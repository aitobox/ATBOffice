"""PowerPoint 2003 Classic Format AutoShape / Picture / Text Box Dialog for Lectern."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtGui import QColor
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
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.shape import Fill, Line, Shape
from atboffice.modules.presentation.models.text import TextBody


def safe_tr(text: str) -> str:
    """Translate UI text safely for FormatShapeDialog."""
    return QCoreApplication.translate("FormatShapeDialog", text)


class ColorButton(QPushButton):
    """Button showing active color swatch and triggering a QColorDialog."""

    colorChanged = Signal(str)

    def __init__(self, initial_color: str = "#000000", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color: str = initial_color
        self.clicked.connect(self._choose_color)
        self.update_style()

    def get_color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        self._color = color
        self.update_style()
        self.colorChanged.emit(self._color)

    def update_style(self) -> None:
        col = self._color or "#FFFFFF"
        if col.startswith("#"):
            qc = QColor(col)
        else:
            qc = QColor("#000000")
        text_color = "#FFFFFF" if qc.lightness() < 128 else "#000000"
        self.setStyleSheet(
            f"QPushButton {{ background-color: {col}; color: {text_color}; "
            "border: 1px solid #7F9DB9; border-radius: 2px; padding: 3px 8px; font-weight: bold; }}"
        )
        self.setText(col.upper())

    def _choose_color(self) -> None:
        init_c = (
            QColor(self._color)
            if self._color and self._color.startswith("#")
            else QColor(Qt.GlobalColor.black)
        )
        chosen = QColorDialog.getColor(init_c, self, safe_tr("Select Color"))
        if chosen.isValid():
            self.set_color(chosen.name().upper())


class ColorsLinesTab(QWidget):
    """Colors and Lines tab for FormatShapeDialog."""

    def __init__(self, shape: Shape, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.shape = shape
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 1. Fill Group
        self.fill_group = QGroupBox(safe_tr("Fill"))
        fill_layout = QFormLayout(self.fill_group)

        init_fill_color = self.shape.fill.color if self.shape.fill.type == "solid" else "#FFFFFF"
        if not init_fill_color or not init_fill_color.startswith("#"):
            init_fill_color = "#336699"
        self.fill_color_btn = ColorButton(init_fill_color)

        init_trans = int(round((1.0 - getattr(self.shape.fill, "alpha", 1.0)) * 100))
        self.transparency_spin = QSpinBox()
        self.transparency_spin.setRange(0, 100)
        self.transparency_spin.setValue(max(0, min(100, init_trans)))
        self.transparency_spin.setSuffix(" %")

        self.fill_color_label = QLabel(safe_tr("Color:"))
        self.transparency_label = QLabel(safe_tr("Transparency:"))
        fill_layout.addRow(self.fill_color_label, self.fill_color_btn)
        fill_layout.addRow(self.transparency_label, self.transparency_spin)
        layout.addWidget(self.fill_group)

        # 2. Line Group
        self.line_group = QGroupBox(safe_tr("Line"))
        line_layout = QGridLayout(self.line_group)

        init_line_color = self.shape.line.color if self.shape.line.type != "none" else "#000000"
        if not init_line_color or not init_line_color.startswith("#"):
            init_line_color = "#000000"
        self.line_color_btn = ColorButton(init_line_color)

        self.line_dash_combo = QComboBox()
        self.line_dash_combo.addItems(["solid", "dash", "dot", "dashDot", "lgDash"])
        cur_dash = getattr(self.shape.line, "dash", "solid") or "solid"
        idx = self.line_dash_combo.findText(cur_dash)
        if idx >= 0:
            self.line_dash_combo.setCurrentIndex(idx)

        self.line_cmpd_combo = QComboBox()
        self.line_cmpd_combo.addItem(safe_tr("Single"), "sng")
        self.line_cmpd_combo.addItem(safe_tr("Double"), "dbl")
        self.line_cmpd_combo.addItem(safe_tr("Thick Thin"), "thickThin")
        self.line_cmpd_combo.addItem(safe_tr("Thin Thick"), "thinThick")
        self.line_cmpd_combo.addItem(safe_tr("Triple"), "tri")

        self.line_weight_spin = QDoubleSpinBox()
        self.line_weight_spin.setRange(0.0, 1584.0)
        self.line_weight_spin.setSingleStep(0.25)
        self.line_weight_spin.setDecimals(2)
        self.line_weight_spin.setValue(getattr(self.shape.line, "width", 0.75))
        self.line_weight_spin.setSuffix(" pt")

        self.line_color_label = QLabel(safe_tr("Color:"))
        self.line_dash_label = QLabel(safe_tr("Dashed:"))
        self.line_style_label = QLabel(safe_tr("Style:"))
        self.line_weight_label = QLabel(safe_tr("Weight:"))

        line_layout.addWidget(self.line_color_label, 0, 0)
        line_layout.addWidget(self.line_color_btn, 0, 1)
        line_layout.addWidget(self.line_style_label, 0, 2)
        line_layout.addWidget(self.line_cmpd_combo, 0, 3)

        line_layout.addWidget(self.line_dash_label, 1, 0)
        line_layout.addWidget(self.line_dash_combo, 1, 1)
        line_layout.addWidget(self.line_weight_label, 1, 2)
        line_layout.addWidget(self.line_weight_spin, 1, 3)

        layout.addWidget(self.line_group)

        # 3. Arrows Group
        self.arrows_group = QGroupBox(safe_tr("Arrows"))
        arrows_layout = QGridLayout(self.arrows_group)

        self.arrow_begin_style = QComboBox()
        self.arrow_begin_style.addItems(["none", "triangle", "stealth", "diamond", "oval", "open"])
        self.arrow_begin_size = QComboBox()
        self.arrow_begin_size.addItems(["small", "med", "large"])

        self.arrow_end_style = QComboBox()
        self.arrow_end_style.addItems(["none", "triangle", "stealth", "diamond", "oval", "open"])
        self.arrow_end_size = QComboBox()
        self.arrow_end_size.addItems(["small", "med", "large"])

        self.arrow_begin_style_lbl = QLabel(safe_tr("Begin style:"))
        self.arrow_begin_size_lbl = QLabel(safe_tr("Begin size:"))
        self.arrow_end_style_lbl = QLabel(safe_tr("End style:"))
        self.arrow_end_size_lbl = QLabel(safe_tr("End size:"))

        arrows_layout.addWidget(self.arrow_begin_style_lbl, 0, 0)
        arrows_layout.addWidget(self.arrow_begin_style, 0, 1)
        arrows_layout.addWidget(self.arrow_end_style_lbl, 0, 2)
        arrows_layout.addWidget(self.arrow_end_style, 0, 3)

        arrows_layout.addWidget(self.arrow_begin_size_lbl, 1, 0)
        arrows_layout.addWidget(self.arrow_begin_size, 1, 1)
        arrows_layout.addWidget(self.arrow_end_size_lbl, 1, 2)
        arrows_layout.addWidget(self.arrow_end_size, 1, 3)

        layout.addWidget(self.arrows_group)
        layout.addStretch()

    def retranslate_ui(self) -> None:
        self.fill_group.setTitle(safe_tr("Fill"))
        self.fill_color_label.setText(safe_tr("Color:"))
        self.transparency_label.setText(safe_tr("Transparency:"))
        self.line_group.setTitle(safe_tr("Line"))
        self.line_color_label.setText(safe_tr("Color:"))
        self.line_dash_label.setText(safe_tr("Dashed:"))
        self.line_style_label.setText(safe_tr("Style:"))
        self.line_weight_label.setText(safe_tr("Weight:"))
        self.arrows_group.setTitle(safe_tr("Arrows"))
        self.arrow_begin_style_lbl.setText(safe_tr("Begin style:"))
        self.arrow_begin_size_lbl.setText(safe_tr("Begin size:"))
        self.arrow_end_style_lbl.setText(safe_tr("End style:"))
        self.arrow_end_size_lbl.setText(safe_tr("End size:"))


class SizeTab(QWidget):
    """Size and rotation tab for FormatShapeDialog."""

    def __init__(self, shape: Shape, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.shape = shape
        self._orig_w = max(0.01, float(shape.w))
        self._orig_h = max(0.01, float(shape.h))
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.size_group = QGroupBox(safe_tr("Size and rotate"))
        size_layout = QGridLayout(self.size_group)

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(0.0, 4000.0)
        self.height_spin.setValue(self.shape.h)
        self.height_spin.setSuffix(" pt")
        self.height_spin.valueChanged.connect(self._on_h_changed)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.0, 4000.0)
        self.width_spin.setValue(self.shape.w)
        self.width_spin.setSuffix(" pt")
        self.width_spin.valueChanged.connect(self._on_w_changed)

        self.rot_spin = QDoubleSpinBox()
        self.rot_spin.setRange(-360.0, 360.0)
        self.rot_spin.setValue(self.shape.rot)
        self.rot_spin.setSuffix("°")

        self.height_lbl = QLabel(safe_tr("Height:"))
        self.width_lbl = QLabel(safe_tr("Width:"))
        self.rot_lbl = QLabel(safe_tr("Rotation:"))

        size_layout.addWidget(self.height_lbl, 0, 0)
        size_layout.addWidget(self.height_spin, 0, 1)
        size_layout.addWidget(self.width_lbl, 0, 2)
        size_layout.addWidget(self.width_spin, 0, 3)
        size_layout.addWidget(self.rot_lbl, 1, 0)
        size_layout.addWidget(self.rot_spin, 1, 1)

        layout.addWidget(self.size_group)

        self.scale_group = QGroupBox(safe_tr("Scale"))
        scale_layout = QVBoxLayout(self.scale_group)
        self.lock_aspect_chk = QCheckBox(safe_tr("Lock aspect ratio"))
        self.lock_aspect_chk.setChecked(bool(getattr(self.shape, "lock_aspect", False)))
        scale_layout.addWidget(self.lock_aspect_chk)
        layout.addWidget(self.scale_group)

        if self.shape.type == "image":
            self.orig_group = QGroupBox(safe_tr("Original size"))
            orig_layout = QHBoxLayout(self.orig_group)
            self.reset_btn = QPushButton(safe_tr("Reset"))
            self.reset_btn.clicked.connect(self._on_reset_pic_size)
            orig_layout.addWidget(self.reset_btn)
            layout.addWidget(self.orig_group)

        layout.addStretch()

    def _on_w_changed(self, new_w: float) -> None:
        if self.lock_aspect_chk.isChecked() and self._orig_w > 0:
            ratio = new_w / self._orig_w
            self.height_spin.blockSignals(True)
            self.height_spin.setValue(round(self._orig_h * ratio, 2))
            self.height_spin.blockSignals(False)

    def _on_h_changed(self, new_h: float) -> None:
        if self.lock_aspect_chk.isChecked() and self._orig_h > 0:
            ratio = new_h / self._orig_h
            self.width_spin.blockSignals(True)
            self.width_spin.setValue(round(self._orig_w * ratio, 2))
            self.width_spin.blockSignals(False)

    def _on_reset_pic_size(self) -> None:
        self.width_spin.setValue(self._orig_w)
        self.height_spin.setValue(self._orig_h)

    def retranslate_ui(self) -> None:
        self.size_group.setTitle(safe_tr("Size and rotate"))
        self.height_lbl.setText(safe_tr("Height:"))
        self.width_lbl.setText(safe_tr("Width:"))
        self.rot_lbl.setText(safe_tr("Rotation:"))
        self.scale_group.setTitle(safe_tr("Scale"))
        self.lock_aspect_chk.setText(safe_tr("Lock aspect ratio"))
        if hasattr(self, "orig_group"):
            self.orig_group.setTitle(safe_tr("Original size"))
            self.reset_btn.setText(safe_tr("Reset"))


class PositionTab(QWidget):
    """Position on slide tab for FormatShapeDialog."""

    def __init__(self, shape: Shape, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.shape = shape
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.pos_group = QGroupBox(safe_tr("Position on slide"))
        pos_layout = QFormLayout(self.pos_group)

        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(-4000.0, 4000.0)
        self.x_spin.setValue(self.shape.x)
        self.x_spin.setSuffix(" pt")

        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(-4000.0, 4000.0)
        self.y_spin.setValue(self.shape.y)
        self.y_spin.setSuffix(" pt")

        self.x_lbl = QLabel(safe_tr("Horizontal:"))
        self.y_lbl = QLabel(safe_tr("Vertical:"))
        self.from_lbl = QLabel(safe_tr("From: Top Left Corner"))
        self.from_lbl.setStyleSheet("color: #666666; font-style: italic;")

        pos_layout.addRow(self.x_lbl, self.x_spin)
        pos_layout.addRow(self.y_lbl, self.y_spin)
        pos_layout.addRow(self.from_lbl)

        layout.addWidget(self.pos_group)
        layout.addStretch()

    def retranslate_ui(self) -> None:
        self.pos_group.setTitle(safe_tr("Position on slide"))
        self.x_lbl.setText(safe_tr("Horizontal:"))
        self.y_lbl.setText(safe_tr("Vertical:"))
        self.from_lbl.setText(safe_tr("From: Top Left Corner"))


class PictureTab(QWidget):
    """Picture tab for FormatShapeDialog (brightness, contrast, crop)."""

    def __init__(self, shape: Shape, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.shape = shape
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Image control
        self.ctrl_group = QGroupBox(safe_tr("Image control"))
        ctrl_layout = QFormLayout(self.ctrl_group)

        self.color_mode_combo = QComboBox()
        self.color_mode_combo.addItem(safe_tr("Automatic"), "auto")
        self.color_mode_combo.addItem(safe_tr("Grayscale"), "gray")
        self.color_mode_combo.addItem(safe_tr("Black & White"), "bi")
        self.color_mode_combo.addItem(safe_tr("Washout"), "wash")

        cur_img = getattr(self.shape, "img", {}) or {}
        cur_mode = cur_img.get("mode", "auto")
        idx = self.color_mode_combo.findData(cur_mode)
        if idx >= 0:
            self.color_mode_combo.setCurrentIndex(idx)

        self.brightness_spin = QSpinBox()
        self.brightness_spin.setRange(-100, 100)
        self.brightness_spin.setValue(int(cur_img.get("bright", 0)))
        self.brightness_spin.setSuffix(" %")

        self.contrast_spin = QSpinBox()
        self.contrast_spin.setRange(-100, 100)
        self.contrast_spin.setValue(int(cur_img.get("contrast", 0)))
        self.contrast_spin.setSuffix(" %")

        self.mode_lbl = QLabel(safe_tr("Color:"))
        self.bright_lbl = QLabel(safe_tr("Brightness:"))
        self.contrast_lbl = QLabel(safe_tr("Contrast:"))

        ctrl_layout.addRow(self.mode_lbl, self.color_mode_combo)
        ctrl_layout.addRow(self.bright_lbl, self.brightness_spin)
        ctrl_layout.addRow(self.contrast_lbl, self.contrast_spin)
        layout.addWidget(self.ctrl_group)

        # Crop from
        self.crop_group = QGroupBox(safe_tr("Crop from"))
        crop_layout = QGridLayout(self.crop_group)

        crop = getattr(self.shape, "crop", None) or {}
        self.crop_left_spin = QDoubleSpinBox()
        self.crop_left_spin.setRange(0.0, 99.0)
        self.crop_left_spin.setValue(float(crop.get("l", 0.0)) * 100.0)
        self.crop_left_spin.setSuffix(" %")

        self.crop_right_spin = QDoubleSpinBox()
        self.crop_right_spin.setRange(0.0, 99.0)
        self.crop_right_spin.setValue(float(crop.get("r", 0.0)) * 100.0)
        self.crop_right_spin.setSuffix(" %")

        self.crop_top_spin = QDoubleSpinBox()
        self.crop_top_spin.setRange(0.0, 99.0)
        self.crop_top_spin.setValue(float(crop.get("t", 0.0)) * 100.0)
        self.crop_top_spin.setSuffix(" %")

        self.crop_bottom_spin = QDoubleSpinBox()
        self.crop_bottom_spin.setRange(0.0, 99.0)
        self.crop_bottom_spin.setValue(float(crop.get("b", 0.0)) * 100.0)
        self.crop_bottom_spin.setSuffix(" %")

        self.crop_left_lbl = QLabel(safe_tr("Left:"))
        self.crop_right_lbl = QLabel(safe_tr("Right:"))
        self.crop_top_lbl = QLabel(safe_tr("Top:"))
        self.crop_bottom_lbl = QLabel(safe_tr("Bottom:"))

        crop_layout.addWidget(self.crop_left_lbl, 0, 0)
        crop_layout.addWidget(self.crop_left_spin, 0, 1)
        crop_layout.addWidget(self.crop_right_lbl, 0, 2)
        crop_layout.addWidget(self.crop_right_spin, 0, 3)

        crop_layout.addWidget(self.crop_top_lbl, 1, 0)
        crop_layout.addWidget(self.crop_top_spin, 1, 1)
        crop_layout.addWidget(self.crop_bottom_lbl, 1, 2)
        crop_layout.addWidget(self.crop_bottom_spin, 1, 3)

        layout.addWidget(self.crop_group)
        layout.addStretch()

    def retranslate_ui(self) -> None:
        self.ctrl_group.setTitle(safe_tr("Image control"))
        self.mode_lbl.setText(safe_tr("Color:"))
        self.bright_lbl.setText(safe_tr("Brightness:"))
        self.contrast_lbl.setText(safe_tr("Contrast:"))
        self.crop_group.setTitle(safe_tr("Crop from"))
        self.crop_left_lbl.setText(safe_tr("Left:"))
        self.crop_right_lbl.setText(safe_tr("Right:"))
        self.crop_top_lbl.setText(safe_tr("Top:"))
        self.crop_bottom_lbl.setText(safe_tr("Bottom:"))


class TextBoxTab(QWidget):
    """Text box and margins tab for FormatShapeDialog."""

    def __init__(self, shape: Shape, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.shape = shape
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        tb = self.shape.text or TextBody()

        # Text layout
        self.align_group = QGroupBox(safe_tr("Text alignment"))
        align_layout = QFormLayout(self.align_group)

        self.vert_anchor_combo = QComboBox()
        self.vert_anchor_combo.addItem(safe_tr("Top"), "t")
        self.vert_anchor_combo.addItem(safe_tr("Middle"), "ctr")
        self.vert_anchor_combo.addItem(safe_tr("Bottom"), "b")
        idx = self.vert_anchor_combo.findData(tb.anchor)
        if idx >= 0:
            self.vert_anchor_combo.setCurrentIndex(idx)

        self.vert_anchor_lbl = QLabel(safe_tr("Text anchor point:"))
        align_layout.addRow(self.vert_anchor_lbl, self.vert_anchor_combo)
        layout.addWidget(self.align_group)

        # Internal margins
        self.margin_group = QGroupBox(safe_tr("Internal margin"))
        margin_layout = QGridLayout(self.margin_group)

        insets = tb.insets if tb and tb.insets else (7.2, 3.6, 7.2, 3.6)
        self.margin_left_spin = QDoubleSpinBox()
        self.margin_left_spin.setRange(0.0, 500.0)
        self.margin_left_spin.setValue(insets[0])
        self.margin_left_spin.setSuffix(" pt")

        self.margin_top_spin = QDoubleSpinBox()
        self.margin_top_spin.setRange(0.0, 500.0)
        self.margin_top_spin.setValue(insets[1])
        self.margin_top_spin.setSuffix(" pt")

        self.margin_right_spin = QDoubleSpinBox()
        self.margin_right_spin.setRange(0.0, 500.0)
        self.margin_right_spin.setValue(insets[2])
        self.margin_right_spin.setSuffix(" pt")

        self.margin_bottom_spin = QDoubleSpinBox()
        self.margin_bottom_spin.setRange(0.0, 500.0)
        self.margin_bottom_spin.setValue(insets[3])
        self.margin_bottom_spin.setSuffix(" pt")

        self.margin_left_lbl = QLabel(safe_tr("Left:"))
        self.margin_right_lbl = QLabel(safe_tr("Right:"))
        self.margin_top_lbl = QLabel(safe_tr("Top:"))
        self.margin_bottom_lbl = QLabel(safe_tr("Bottom:"))

        margin_layout.addWidget(self.margin_left_lbl, 0, 0)
        margin_layout.addWidget(self.margin_left_spin, 0, 1)
        margin_layout.addWidget(self.margin_right_lbl, 0, 2)
        margin_layout.addWidget(self.margin_right_spin, 0, 3)

        margin_layout.addWidget(self.margin_top_lbl, 1, 0)
        margin_layout.addWidget(self.margin_top_spin, 1, 1)
        margin_layout.addWidget(self.margin_bottom_lbl, 1, 2)
        margin_layout.addWidget(self.margin_bottom_spin, 1, 3)

        layout.addWidget(self.margin_group)

        # Wrapping and AutoFit
        self.wrap_group = QGroupBox(safe_tr("Text options"))
        wrap_layout = QVBoxLayout(self.wrap_group)

        self.word_wrap_chk = QCheckBox(safe_tr("Word wrap text in AutoShape"))
        self.word_wrap_chk.setChecked(bool(tb.wrap))
        wrap_layout.addWidget(self.word_wrap_chk)

        self.vert_text_chk = QCheckBox(safe_tr("Rotate text within AutoShape by 90° (Vertical)"))
        self.vert_text_chk.setChecked(tb.vert == "vert")
        wrap_layout.addWidget(self.vert_text_chk)

        layout.addWidget(self.wrap_group)
        layout.addStretch()

    def retranslate_ui(self) -> None:
        self.align_group.setTitle(safe_tr("Text alignment"))
        self.vert_anchor_lbl.setText(safe_tr("Text anchor point:"))
        self.margin_group.setTitle(safe_tr("Internal margin"))
        self.margin_left_lbl.setText(safe_tr("Left:"))
        self.margin_right_lbl.setText(safe_tr("Right:"))
        self.margin_top_lbl.setText(safe_tr("Top:"))
        self.margin_bottom_lbl.setText(safe_tr("Bottom:"))
        self.wrap_group.setTitle(safe_tr("Text options"))
        self.word_wrap_chk.setText(safe_tr("Word wrap text in AutoShape"))
        self.vert_text_chk.setText(safe_tr("Rotate text within AutoShape by 90° (Vertical)"))


class WebTab(QWidget):
    """Web / Alternative text tab for FormatShapeDialog."""

    def __init__(self, shape: Shape, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.shape = shape
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.alt_group = QGroupBox(safe_tr("Alternative text"))
        alt_layout = QVBoxLayout(self.alt_group)

        self.alt_text_edit = QPlainTextEdit()
        self.alt_text_edit.setPlainText(str(getattr(self.shape, "alt", "") or ""))
        self.alt_text_edit.setPlaceholderText(safe_tr("Enter text describing this object..."))
        alt_layout.addWidget(self.alt_text_edit)

        self.note_lbl = QLabel(
            safe_tr("Screen readers and web pages use alternative text to describe the object.")
        )
        self.note_lbl.setWordWrap(True)
        self.note_lbl.setStyleSheet("color: #666666; font-size: 11px;")
        alt_layout.addWidget(self.note_lbl)

        layout.addWidget(self.alt_group)

    def retranslate_ui(self) -> None:
        self.alt_group.setTitle(safe_tr("Alternative text"))
        self.alt_text_edit.setPlaceholderText(safe_tr("Enter text describing this object..."))
        self.note_lbl.setText(
            safe_tr("Screen readers and web pages use alternative text to describe the object.")
        )


class FormatShapeDialog(QDialog):
    """PowerPoint 2003 Classic Format AutoShape Dialog."""

    def __init__(
        self,
        shapes: list[Shape],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.shapes: list[Shape] = shapes or [Shape(id="temp")]
        self.s0: Shape = self.shapes[0]
        self._init_ui()

    def _init_ui(self) -> None:
        self.resize(520, 480)
        self._update_title()

        layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()

        # Tabs
        self.color_lines_tab = ColorsLinesTab(self.s0, self)
        self.size_tab = SizeTab(self.s0, self)
        self.pos_tab = PositionTab(self.s0, self)

        self.tab_widget.addTab(self.color_lines_tab, safe_tr("Colors and Lines"))
        self.tab_widget.addTab(self.size_tab, safe_tr("Size"))
        self.tab_widget.addTab(self.pos_tab, safe_tr("Position"))

        self.pic_tab: PictureTab | None = None
        if self.s0.type == "image":
            self.pic_tab = PictureTab(self.s0, self)
            self.tab_widget.addTab(self.pic_tab, safe_tr("Picture"))

        self.text_tab = TextBoxTab(self.s0, self)
        self.tab_widget.addTab(self.text_tab, safe_tr("Text Box"))

        self.web_tab = WebTab(self.s0, self)
        self.tab_widget.addTab(self.web_tab, safe_tr("Web"))

        layout.addWidget(self.tab_widget)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _update_title(self) -> None:
        if self.s0.type == "image":
            title = safe_tr("Format Picture")
        elif self.s0.type == "line":
            title = safe_tr("Format Line")
        elif self.s0.type == "text":
            title = safe_tr("Format Text Box")
        else:
            title = safe_tr("Format AutoShape")
        self.setWindowTitle(title)

    def apply_changes(self) -> None:
        """Apply dialog input changes to target shapes."""
        fill_color = self.color_lines_tab.fill_color_btn.get_color()
        transparency = self.color_lines_tab.transparency_spin.value()
        alpha = max(0.0, min(1.0, round(1.0 - (transparency / 100.0), 2)))

        line_color = self.color_lines_tab.line_color_btn.get_color()
        line_weight = self.color_lines_tab.line_weight_spin.value()
        line_dash = self.color_lines_tab.line_dash_combo.currentText()

        new_w = max(1.0, self.size_tab.width_spin.value())
        new_h = max(1.0, self.size_tab.height_spin.value())
        rot = self.size_tab.rot_spin.value()
        lock_aspect = self.size_tab.lock_aspect_chk.isChecked()

        new_x = self.pos_tab.x_spin.value()
        new_y = self.pos_tab.y_spin.value()

        # Text box settings
        anchor = self.text_tab.vert_anchor_combo.currentData() or "t"
        insets = (
            self.text_tab.margin_left_spin.value(),
            self.text_tab.margin_top_spin.value(),
            self.text_tab.margin_right_spin.value(),
            self.text_tab.margin_bottom_spin.value(),
        )
        wrap = self.text_tab.word_wrap_chk.isChecked()
        vert = "vert" if self.text_tab.vert_text_chk.isChecked() else None

        alt_text = self.web_tab.alt_text_edit.toPlainText().strip()

        for s in self.shapes:
            # Colors & lines
            s.fill = Fill.solid(color=fill_color, alpha=alpha)
            s.line = Line(color=line_color, width=line_weight, dash=line_dash)

            # Size & Position
            s.w = new_w
            s.h = new_h
            s.rot = rot
            setattr(s, "lock_aspect", lock_aspect)
            s.x = new_x
            s.y = new_y

            # Picture tab
            if self.pic_tab is not None and s.type == "image":
                mode = self.pic_tab.color_mode_combo.currentData()
                bright = self.pic_tab.brightness_spin.value()
                contrast = self.pic_tab.contrast_spin.value()
                setattr(s, "img", {"mode": mode, "bright": bright, "contrast": contrast})

                crop_l = self.pic_tab.crop_left_spin.value() / 100.0
                crop_t = self.pic_tab.crop_top_spin.value() / 100.0
                crop_r = self.pic_tab.crop_right_spin.value() / 100.0
                crop_b = self.pic_tab.crop_bottom_spin.value() / 100.0
                s.crop = {"l": crop_l, "t": crop_t, "r": crop_r, "b": crop_b}

            # Text box
            if s.text is None:
                s.text = TextBody()
            s.text.anchor = anchor
            s.text.insets = insets
            s.text.wrap = wrap
            s.text.vert = vert

            # Web / Alt
            setattr(s, "alt", alt_text)

    def _on_accept(self) -> None:
        self.apply_changes()
        self.accept()

    def retranslate_ui(self) -> None:
        self._update_title()
        self.tab_widget.setTabText(0, safe_tr("Colors and Lines"))
        self.tab_widget.setTabText(1, safe_tr("Size"))
        self.tab_widget.setTabText(2, safe_tr("Position"))
        idx = 3
        if self.pic_tab is not None:
            self.tab_widget.setTabText(idx, safe_tr("Picture"))
            self.pic_tab.retranslate_ui()
            idx += 1
        self.tab_widget.setTabText(idx, safe_tr("Text Box"))
        self.text_tab.retranslate_ui()
        idx += 1
        self.tab_widget.setTabText(idx, safe_tr("Web"))
        self.web_tab.retranslate_ui()

        self.color_lines_tab.retranslate_ui()
        self.size_tab.retranslate_ui()
        self.pos_tab.retranslate_ui()
