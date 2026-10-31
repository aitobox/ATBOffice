"""Background and Fill Effects dialogs for Lectern presentations.

Replicates classic Office 2003 / .vibeoffice background formatting:
- Solid color fills (Automatic, Theme colors, Standard colors, More colors)
- Fill effects:
  1. Gradient (One color, Two colors, 21 Presets, 6 Shading styles, 4 Variants, Transparency)
  2. Texture (18 procedural textures + external texture images)
  3. Pattern (54 ECMA-376 / Office 2003 preset patterns with custom FG/BG)
  4. Picture (Local picture files with tiled/stretched modes)
- Actions: Apply (current slide), Apply to All (entire presentation & designs), Preview, Cancel.
- Option to omit background graphics from master slide.
"""

from __future__ import annotations

import copy
import os
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.shape import Fill
from atboffice.modules.presentation.views.background_renderer import (
    GRAD_PRESETS,
    TEXTURE_KEY_MAP,
    TEXTURE_NAMES,
    get_procedural_texture,
    paint_fill_rect,
)
from atboffice.modules.spreadsheet.dialogs.pattern_defs import (
    PATTERN_NAMES,
    PATTERNS,
    create_pattern_pixmap,
)

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.designs import DesignTemplate
    from atboffice.modules.presentation.models.presentation import Presentation
    from atboffice.modules.presentation.models.slide import Slide


def safe_tr(text: str) -> str:
    """Translate UI text with fallback to English."""
    app = QCoreApplication.instance()
    if app:
        translated = app.translate("BackgroundDialog", text)
        if translated and translated != text:
            return translated
    return text


# ==============================================================================
# Helper Widgets
# ==============================================================================


class ColorSwatchButton(QPushButton):
    """Square button displaying a solid color swatch with click-to-pick capability."""

    colorChanged = Signal(str)

    def __init__(self, initial_color: str = "#3366CC", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = initial_color
        self.setFixedSize(56, 26)
        self._update_appearance()
        self.clicked.connect(self._choose_color)

    def get_color(self) -> str:
        return self._color

    def set_color(self, color_hex: str) -> None:
        if self._color != color_hex:
            self._color = color_hex
            self._update_appearance()
            self.colorChanged.emit(self._color)

    def _choose_color(self) -> None:
        col = QColorDialog.getColor(QColor(self._color), self, safe_tr("选择颜色"))
        if col.isValid():
            self.set_color(col.name(QColor.NameFormat.HexRgb).upper())

    def _update_appearance(self) -> None:
        c = self._color if self._color.startswith("#") else "#3366CC"
        self.setStyleSheet(
            f"QPushButton {{ background-color: {c}; border: 1.5px solid #777777; "
            "border-radius: 2px; } "
            "QPushButton:hover { border: 1.5px solid #000000; }"
        )


class FillSampleWidget(QFrame):
    """Live preview swatch for displaying the current fill."""

    def __init__(
        self,
        fill: Fill | None = None,
        design: DesignTemplate | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.fill: Fill | None = copy.deepcopy(fill) if fill else None
        self.design = design
        self.setFixedSize(120, 100)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        self.setLineWidth(1)

    def set_fill(self, fill: Fill | None) -> None:
        self.fill = copy.deepcopy(fill) if fill else None
        self.update()

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        try:
            r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
            paint_fill_rect(painter, r, self.fill, self.design)
            painter.setPen(QPen(QColor(180, 180, 180), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)
        finally:
            painter.end()


class SlideBackgroundPreview(QFrame):
    """Miniature slide canvas preview for the main BackgroundDialog."""

    def __init__(
        self,
        slide: Slide | None = None,
        presentation: Presentation | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.slide = slide
        self.presentation = presentation
        self.current_fill: Fill | None = copy.deepcopy(slide.bg) if (slide and slide.bg) else None
        self.omit_master: bool = bool(slide.hide_master) if slide else False
        self.setFixedSize(220, 140)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        self.setLineWidth(1)

    def set_state(self, fill: Fill | None, omit_master: bool) -> None:
        self.current_fill = copy.deepcopy(fill) if fill else None
        self.omit_master = omit_master
        self.update()

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)

            design = None
            if self.presentation and self.slide:
                design = self.presentation.get_design_for_slide(self.slide)

            # 1. Fill slide background
            paint_fill_rect(painter, rect, self.current_fill, design)

            # 2. Border
            painter.setPen(QPen(QColor(150, 150, 150), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            # 3. Simple placeholder lines indicating a slide
            if self.slide and not self.omit_master:
                painter.setPen(QPen(QColor(0, 0, 0, 40), 1, Qt.PenStyle.DashLine))
                painter.drawRect(rect.adjusted(15, 15, -15, -60))
                painter.drawRect(rect.adjusted(15, 85, -15, -15))
        finally:
            painter.end()


# ==============================================================================
# Fill Effects Dialog
# ==============================================================================


class FillEffectsDialog(QDialog):
    """Office 2003 4-tab Fill Effects dialog (Gradient, Texture, Pattern, Picture)."""

    def __init__(
        self,
        initial_fill: Fill | None = None,
        design: DesignTemplate | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.design = design
        self.current_fill: Fill = (
            copy.deepcopy(initial_fill)
            if initial_fill and initial_fill.type != "none"
            else Fill.solid("#3366CC")
        )

        self.setWindowTitle(safe_tr("填充效果"))
        self.resize(540, 420)
        self.setModal(True)

        self._build_ui()
        self._load_initial_fill()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # Bottom row: Sample Box & OK/Cancel buttons
        self.sample_widget = FillSampleWidget(self.current_fill, self.design, self)

        # Tab Widget
        self.tab_widget = QTabWidget(self)
        self.tab_grad = QWidget()
        self.tab_tex = QWidget()
        self.tab_patt = QWidget()
        self.tab_pic = QWidget()

        self._build_gradient_tab()
        self._build_texture_tab()
        self._build_pattern_tab()
        self._build_picture_tab()

        self.tab_widget.addTab(self.tab_grad, safe_tr("渐变(&G)"))
        self.tab_widget.addTab(self.tab_tex, safe_tr("纹理(&T)"))
        self.tab_widget.addTab(self.tab_patt, safe_tr("图案(&P)"))
        self.tab_widget.addTab(self.tab_pic, safe_tr("图片(&I)"))

        root_layout.addWidget(self.tab_widget)

        # Bottom row: Sample Box & OK/Cancel buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(16)

        sample_box = QGroupBox(safe_tr("示例:"), self)
        sample_vbox = QVBoxLayout(sample_box)
        sample_vbox.setContentsMargins(8, 8, 8, 8)
        sample_vbox.addWidget(self.sample_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        bottom_layout.addWidget(sample_box)

        bottom_layout.addStretch()

        btn_vbox = QVBoxLayout()
        btn_vbox.setSpacing(8)
        self.btn_ok = QPushButton(safe_tr("确定"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)

        self.btn_cancel = QPushButton(safe_tr("取消"), self)
        self.btn_cancel.clicked.connect(self.reject)

        btn_vbox.addWidget(self.btn_ok)
        btn_vbox.addWidget(self.btn_cancel)
        bottom_layout.addLayout(btn_vbox)

        root_layout.addLayout(bottom_layout)

    # --------------------------------------------------------------------------
    # Tab 1: Gradient
    # --------------------------------------------------------------------------
    def _build_gradient_tab(self) -> None:
        layout = QHBoxLayout(self.tab_grad)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Left Column: Colors & Transparency
        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        # Colors Group
        self.grp_colors = QGroupBox(safe_tr("颜色"), self.tab_grad)
        colors_vbox = QVBoxLayout(self.grp_colors)
        colors_vbox.setSpacing(6)

        self.radio_one_col = QRadioButton(safe_tr("单色(&O)"), self.grp_colors)
        self.radio_two_col = QRadioButton(safe_tr("双色(&T)"), self.grp_colors)
        self.radio_preset = QRadioButton(safe_tr("预设(&R)"), self.grp_colors)
        self.radio_two_col.setChecked(True)

        self.color_mode_group = QButtonGroup(self.grp_colors)
        self.color_mode_group.addButton(self.radio_one_col, 1)
        self.color_mode_group.addButton(self.radio_two_col, 2)
        self.color_mode_group.addButton(self.radio_preset, 3)
        self.color_mode_group.idClicked.connect(self._on_grad_mode_changed)

        colors_vbox.addWidget(self.radio_one_col)
        colors_vbox.addWidget(self.radio_two_col)
        colors_vbox.addWidget(self.radio_preset)

        # Color 1 & 2 rows
        self.row_col1 = QHBoxLayout()
        self.lbl_col1 = QLabel(safe_tr("颜色 1(&1):"), self.grp_colors)
        self.btn_col1 = ColorSwatchButton("#FFFFFF", self.grp_colors)
        self.btn_col1.colorChanged.connect(self._refresh_gradient)
        self.row_col1.addWidget(self.lbl_col1)
        self.row_col1.addWidget(self.btn_col1)
        colors_vbox.addLayout(self.row_col1)

        self.row_col2 = QHBoxLayout()
        self.lbl_col2 = QLabel(safe_tr("颜色 2(&2):"), self.grp_colors)
        self.btn_col2 = ColorSwatchButton("#3366CC", self.grp_colors)
        self.btn_col2.colorChanged.connect(self._refresh_gradient)
        self.row_col2.addWidget(self.lbl_col2)
        self.row_col2.addWidget(self.btn_col2)
        colors_vbox.addLayout(self.row_col2)

        # Dark / Light slider for one-color mode
        self.dark_light_box = QHBoxLayout()
        self.lbl_dark = QLabel(safe_tr("变深"), self.grp_colors)
        self.slider_dark = QSlider(Qt.Orientation.Horizontal, self.grp_colors)
        self.slider_dark.setRange(0, 100)
        self.slider_dark.setValue(50)
        self.slider_dark.valueChanged.connect(self._refresh_gradient)
        self.lbl_light = QLabel(safe_tr("变浅"), self.grp_colors)
        self.dark_light_box.addWidget(self.lbl_dark)
        self.dark_light_box.addWidget(self.slider_dark)
        self.dark_light_box.addWidget(self.lbl_light)
        colors_vbox.addLayout(self.dark_light_box)
        self._toggle_dark_light_visible(False)

        # Preset Combobox
        self.row_preset = QHBoxLayout()
        self.lbl_preset = QLabel(safe_tr("预设颜色(&E):"), self.grp_colors)
        self.combo_presets = QComboBox(self.grp_colors)
        for name, _ in GRAD_PRESETS:
            self.combo_presets.addItem(safe_tr(name))
        self.combo_presets.currentIndexChanged.connect(self._refresh_gradient)
        self.row_preset.addWidget(self.lbl_preset)
        self.row_preset.addWidget(self.combo_presets)
        colors_vbox.addLayout(self.row_preset)
        self._toggle_preset_visible(False)

        left_col.addWidget(self.grp_colors)

        # Transparency Group
        self.grp_trans = QGroupBox(safe_tr("透明度"), self.tab_grad)
        trans_grid = QGridLayout(self.grp_trans)
        trans_grid.setContentsMargins(8, 8, 8, 8)
        self.lbl_from = QLabel(safe_tr("从(&F):"), self.grp_trans)
        self.spin_from = QSpinBox(self.grp_trans)
        self.spin_from.setRange(0, 100)
        self.spin_from.setSuffix(" %")
        self.spin_from.valueChanged.connect(self._refresh_gradient)

        self.lbl_to = QLabel(safe_tr("到(&T):"), self.grp_trans)
        self.spin_to = QSpinBox(self.grp_trans)
        self.spin_to.setRange(0, 100)
        self.spin_to.setSuffix(" %")
        self.spin_to.valueChanged.connect(self._refresh_gradient)

        trans_grid.addWidget(self.lbl_from, 0, 0)
        trans_grid.addWidget(self.spin_from, 0, 1)
        trans_grid.addWidget(self.lbl_to, 1, 0)
        trans_grid.addWidget(self.spin_to, 1, 1)
        left_col.addWidget(self.grp_trans)

        layout.addLayout(left_col, stretch=1)

        # Right Column: Shading Styles & Variants
        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        self.grp_shading = QGroupBox(safe_tr("底纹样式"), self.tab_grad)
        shading_vbox = QVBoxLayout(self.grp_shading)
        shading_vbox.setSpacing(4)

        self.radio_horz = QRadioButton(safe_tr("水平(&H)"), self.grp_shading)
        self.radio_vert = QRadioButton(safe_tr("垂直(&V)"), self.grp_shading)
        self.radio_dup = QRadioButton(safe_tr("对角向上(&U)"), self.grp_shading)
        self.radio_ddn = QRadioButton(safe_tr("对角向下(&D)"), self.grp_shading)
        self.radio_corner = QRadioButton(safe_tr("角部(&C)"), self.grp_shading)
        self.radio_center = QRadioButton(safe_tr("中心(&M)"), self.grp_shading)
        self.radio_horz.setChecked(True)

        self.shading_group = QButtonGroup(self.grp_shading)
        shading_buttons = [
            self.radio_horz,
            self.radio_vert,
            self.radio_dup,
            self.radio_ddn,
            self.radio_corner,
            self.radio_center,
        ]
        for i, rb in enumerate(shading_buttons):
            self.shading_group.addButton(rb, i)
            shading_vbox.addWidget(rb)
        self.shading_group.idClicked.connect(self._on_shading_style_changed)

        right_col.addWidget(self.grp_shading)

        # Variants Grid
        self.grp_variants = QGroupBox(safe_tr("变体"), self.tab_grad)
        variants_grid = QGridLayout(self.grp_variants)
        variants_grid.setSpacing(6)

        self.variant_buttons: list[QToolButton] = []
        self.selected_variant_idx: int = 0
        for i in range(4):
            btn = QToolButton(self.grp_variants)
            btn.setFixedSize(48, 48)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, idx=i: self._select_variant(idx))
            variants_grid.addWidget(btn, i // 2, i % 2)
            self.variant_buttons.append(btn)
        self.variant_buttons[0].setChecked(True)

        right_col.addWidget(self.grp_variants)
        layout.addLayout(right_col, stretch=1)

    def _toggle_dark_light_visible(self, visible: bool) -> None:
        self.lbl_dark.setVisible(visible)
        self.slider_dark.setVisible(visible)
        self.lbl_light.setVisible(visible)

    def _toggle_preset_visible(self, visible: bool) -> None:
        self.lbl_preset.setVisible(visible)
        self.combo_presets.setVisible(visible)

    def _on_grad_mode_changed(self, mode_id: int) -> None:
        if mode_id == 1:  # One color
            self.lbl_col1.setVisible(True)
            self.btn_col1.setVisible(True)
            self.lbl_col2.setVisible(False)
            self.btn_col2.setVisible(False)
            self._toggle_dark_light_visible(True)
            self._toggle_preset_visible(False)
        elif mode_id == 2:  # Two colors
            self.lbl_col1.setVisible(True)
            self.btn_col1.setVisible(True)
            self.lbl_col2.setVisible(True)
            self.btn_col2.setVisible(True)
            self._toggle_dark_light_visible(False)
            self._toggle_preset_visible(False)
        else:  # Preset
            self.lbl_col1.setVisible(False)
            self.btn_col1.setVisible(False)
            self.lbl_col2.setVisible(False)
            self.btn_col2.setVisible(False)
            self._toggle_dark_light_visible(False)
            self._toggle_preset_visible(True)
        self._refresh_gradient()

    def _on_shading_style_changed(self, _id: int) -> None:
        self.selected_variant_idx = 0
        self._refresh_gradient()

    def _select_variant(self, idx: int) -> None:
        self.selected_variant_idx = idx
        for i, btn in enumerate(self.variant_buttons):
            btn.setChecked(i == idx)
        self._refresh_gradient(update_variants_only=False)

    def _build_gradient_fill_variant(self, variant_idx: int) -> Fill:
        """Construct a Fill object for a specific variant index (0..3)."""
        mode = self.color_mode_group.checkedId()
        shading_id = self.shading_group.checkedId()
        tr_from = 1.0 - (self.spin_from.value() / 100.0)
        tr_to = 1.0 - (self.spin_to.value() / 100.0)

        # Style keys: horz=0, vert=1, dup=2, ddn=3, corner=4, center=5
        shading_styles = ["horz", "vert", "dup", "ddn", "corner", "center"]
        style = shading_styles[shading_id] if 0 <= shading_id < len(shading_styles) else "horz"

        # Determine colors & stops
        if mode == 3:  # Preset
            p_idx = max(0, min(len(GRAD_PRESETS) - 1, self.combo_presets.currentIndex()))
            _, preset_stops = GRAD_PRESETS[p_idx]
            stops = [{"p": p, "c": c, "a": 1.0} for p, c in preset_stops]
        elif mode == 1:  # One color
            base_col = QColor(self.btn_col1.get_color())
            factor = self.slider_dark.value() / 100.0  # 0.0 (dark) .. 1.0 (light)
            if factor < 0.5:
                # darken
                adj_col = base_col.darker(int(100 + (0.5 - factor) * 200))
            else:
                # lighten
                adj_col = base_col.lighter(int(100 + (factor - 0.5) * 200))
            stops = [
                {"p": 0.0, "c": base_col.name(QColor.NameFormat.HexRgb).upper(), "a": tr_from},
                {"p": 1.0, "c": adj_col.name(QColor.NameFormat.HexRgb).upper(), "a": tr_to},
            ]
        else:  # Two colors
            stops = [
                {"p": 0.0, "c": self.btn_col1.get_color(), "a": tr_from},
                {"p": 1.0, "c": self.btn_col2.get_color(), "a": tr_to},
            ]

        # Apply variant transformations matching Office 2003
        if variant_idx in (1, 3):
            stops = [
                {"p": round(1.0 - s["p"], 2), "c": s["c"], "a": s["a"]}
                for s in reversed(stops)
            ]
        if variant_idx >= 2:
            # Symmetrical reflected gradient
            half1 = [
                {"p": round(s["p"] / 2.0, 2), "c": s["c"], "a": s["a"]}
                for s in stops
            ]
            half2 = [
                {"p": round(1.0 - s["p"] / 2.0, 2), "c": s["c"], "a": s["a"]}
                for s in reversed(stops[1:])
            ]
            stops = half1 + half2

        ang_map = {
            "horz": 90.0,
            "vert": 0.0,
            "dup": 315.0,
            "ddn": 45.0,
            "corner": 0.0,
            "center": 0.0,
        }
        path = "circle" if style == "center" else ("rect" if style == "corner" else "lin")
        return Fill.gradient(stops=stops, angle=ang_map.get(style, 90.0), path=path)

    def _refresh_gradient(self, update_variants_only: bool = False) -> None:
        # 1. Update variant button icons
        for v_idx in range(4):
            v_fill = self._build_gradient_fill_variant(v_idx)
            pix = QPixmap(48, 48)
            p = QPainter(pix)
            paint_fill_rect(p, QRectF(0, 0, 48, 48), v_fill, self.design)
            p.end()
            self.variant_buttons[v_idx].setIcon(QIcon(pix))
            self.variant_buttons[v_idx].setIconSize(QSize(44, 44))

        # 2. Update current active fill and sample
        active_fill = self._build_gradient_fill_variant(self.selected_variant_idx)
        self.current_fill = active_fill
        if hasattr(self, "sample_widget"):
            self.sample_widget.set_fill(self.current_fill)

    # --------------------------------------------------------------------------
    # Tab 2: Texture
    # --------------------------------------------------------------------------
    def _build_texture_tab(self) -> None:
        layout = QVBoxLayout(self.tab_tex)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        lbl = QLabel(safe_tr("纹理(&X):"), self.tab_tex)
        layout.addWidget(lbl)

        scroll = QScrollArea(self.tab_tex)
        scroll.setWidgetResizable(True)
        container = QWidget()
        tex_grid = QGridLayout(container)
        tex_grid.setSpacing(6)

        self.texture_buttons: list[QToolButton] = []
        self.selected_texture_name = TEXTURE_NAMES[0]

        for i, tex_name in enumerate(TEXTURE_NAMES):
            btn = QToolButton(container)
            btn.setFixedSize(50, 50)
            btn.setCheckable(True)
            btn.setToolTip(safe_tr(tex_name))
            pix = get_procedural_texture(tex_name)
            btn.setIcon(QIcon(pix))
            btn.setIconSize(QSize(46, 46))
            btn.clicked.connect(lambda _, n=tex_name: self._on_texture_selected(n))
            tex_grid.addWidget(btn, i // 6, i % 6)
            self.texture_buttons.append(btn)

        self.texture_buttons[0].setChecked(True)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        self.lbl_selected_tex = QLabel(safe_tr(self.selected_texture_name), self.tab_tex)
        self.lbl_selected_tex.setStyleSheet("font-weight: bold; color: #333333;")
        layout.addWidget(self.lbl_selected_tex)

        self.btn_other_tex = QPushButton(safe_tr("其他纹理(&O)..."), self.tab_tex)
        self.btn_other_tex.clicked.connect(self._choose_other_texture)
        layout.addWidget(self.btn_other_tex, alignment=Qt.AlignmentFlag.AlignLeft)

    def _on_texture_selected(self, name: str) -> None:
        self.selected_texture_name = name
        norm_key = TEXTURE_KEY_MAP.get(name, name)
        for btn in self.texture_buttons:
            btn.setChecked(btn.toolTip() == safe_tr(name))
        self.lbl_selected_tex.setText(safe_tr(name))
        self.current_fill = Fill.image_fill(image_path=norm_key, tile=True)
        self.sample_widget.set_fill(self.current_fill)

    def _choose_other_texture(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            safe_tr("选择纹理图片"),
            "",
            safe_tr("图片文件 (*.png *.jpg *.jpeg *.bmp *.webp *.svg);;所有文件 (*.*)"),
        )
        if path and os.path.exists(path):
            name = os.path.basename(path)
            self.selected_texture_name = name
            for btn in self.texture_buttons:
                btn.setChecked(False)
            self.lbl_selected_tex.setText(name)
            self.current_fill = Fill.image_fill(image_path=path, tile=True)
            self.sample_widget.set_fill(self.current_fill)

    # --------------------------------------------------------------------------
    # Tab 3: Pattern
    # --------------------------------------------------------------------------
    def _build_pattern_tab(self) -> None:
        layout = QVBoxLayout(self.tab_patt)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        lbl = QLabel(safe_tr("图案(&P):"), self.tab_patt)
        layout.addWidget(lbl)

        scroll = QScrollArea(self.tab_patt)
        scroll.setWidgetResizable(True)
        container = QWidget()
        patt_grid = QGridLayout(container)
        patt_grid.setSpacing(4)

        self.patt_buttons: dict[str, QToolButton] = {}
        self.selected_pattern_key = "pct50"

        # Row with Foreground and Background Colors
        color_row = QHBoxLayout()
        color_row.setSpacing(12)
        lbl_fg = QLabel(safe_tr("前景色(&G):"), self.tab_patt)
        self.btn_patt_fg = ColorSwatchButton("#000000", self.tab_patt)
        self.btn_patt_fg.colorChanged.connect(self._refresh_pattern_grid)

        lbl_bg = QLabel(safe_tr("背景色(&B):"), self.tab_patt)
        self.btn_patt_bg = ColorSwatchButton("#FFFFFF", self.tab_patt)
        self.btn_patt_bg.colorChanged.connect(self._refresh_pattern_grid)

        color_row.addWidget(lbl_fg)
        color_row.addWidget(self.btn_patt_fg)
        color_row.addSpacing(16)
        color_row.addWidget(lbl_bg)
        color_row.addWidget(self.btn_patt_bg)
        color_row.addStretch()

        # Build 54 pattern grid buttons
        for i, (k, _) in enumerate(PATTERNS.items()):
            btn = QToolButton(container)
            btn.setFixedSize(36, 36)
            btn.setCheckable(True)
            btn.setToolTip(safe_tr(PATTERN_NAMES.get(k, k)))
            btn.clicked.connect(lambda _, key=k: self._on_pattern_selected(key))
            patt_grid.addWidget(btn, i // 6, i % 6)
            self.patt_buttons[k] = btn

        self.patt_buttons["pct50"].setChecked(True)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        self.lbl_selected_patt = QLabel(safe_tr(PATTERN_NAMES.get("pct50", "50%")), self.tab_patt)
        self.lbl_selected_patt.setStyleSheet("font-weight: bold; color: #333333;")
        layout.addWidget(self.lbl_selected_patt)
        layout.addLayout(color_row)

        self._refresh_pattern_grid()

    def _refresh_pattern_grid(self) -> None:
        fg = self.btn_patt_fg.get_color()
        bg = self.btn_patt_bg.get_color()
        for k, btn in self.patt_buttons.items():
            pix = create_pattern_pixmap(k, fg, bg, (32, 32))
            btn.setIcon(QIcon(pix))
            btn.setIconSize(QSize(32, 32))

        self.current_fill = Fill.pattern_fill(prst=self.selected_pattern_key, fg=fg, bg=bg)
        if hasattr(self, "sample_widget"):
            self.sample_widget.set_fill(self.current_fill)

    def _on_pattern_selected(self, key: str) -> None:
        self.selected_pattern_key = key
        for k, btn in self.patt_buttons.items():
            btn.setChecked(k == key)
        self.lbl_selected_patt.setText(safe_tr(PATTERN_NAMES.get(key, key)))
        self._refresh_pattern_grid()

    # --------------------------------------------------------------------------
    # Tab 4: Picture
    # --------------------------------------------------------------------------
    def _build_picture_tab(self) -> None:
        layout = QVBoxLayout(self.tab_pic)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.btn_select_pic = QPushButton(safe_tr("选择图片(&S)..."), self.tab_pic)
        self.btn_select_pic.clicked.connect(self._choose_picture)
        layout.addWidget(self.btn_select_pic, alignment=Qt.AlignmentFlag.AlignLeft)

        self.lbl_pic_path = QLabel(safe_tr("尚未选择图片"), self.tab_pic)
        self.lbl_pic_path.setStyleSheet("color: #666666;")
        layout.addWidget(self.lbl_pic_path)

        self.chk_tile_pic = QCheckBox(safe_tr("平铺图片为纹理(&T)"), self.tab_pic)
        self.chk_tile_pic.toggled.connect(self._on_pic_tile_toggled)
        layout.addWidget(self.chk_tile_pic)

        self.selected_picture_path = ""
        layout.addStretch()

    def _choose_picture(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            safe_tr("选择图片"),
            "",
            safe_tr("图片文件 (*.png *.jpg *.jpeg *.bmp *.webp *.svg);;所有文件 (*.*)"),
        )
        if path and os.path.exists(path):
            self.selected_picture_path = path
            self.lbl_pic_path.setText(os.path.basename(path))
            self.current_fill = Fill.image_fill(
                image_path=path, tile=self.chk_tile_pic.isChecked()
            )
            self.sample_widget.set_fill(self.current_fill)

    def _on_pic_tile_toggled(self, checked: bool) -> None:
        if self.selected_picture_path:
            self.current_fill = Fill.image_fill(
                image_path=self.selected_picture_path, tile=checked
            )
            self.sample_widget.set_fill(self.current_fill)

    # --------------------------------------------------------------------------
    # Initial Load & Public API
    # --------------------------------------------------------------------------
    def _load_initial_fill(self) -> None:
        f = self.current_fill
        if f.type == "patt":
            self.tab_widget.setCurrentIndex(2)
            self.selected_pattern_key = f.pattern or "pct50"
            if f.fg:
                self.btn_patt_fg.set_color(f.fg)
            if f.bg:
                self.btn_patt_bg.set_color(f.bg)
            self._on_pattern_selected(self.selected_pattern_key)
        elif f.type == "img":
            if f.tile:
                self.tab_widget.setCurrentIndex(1)
                img_k = getattr(f, "image_path", "")
                norm_name = TEXTURE_KEY_MAP.get(img_k, img_k)
                if norm_name in TEXTURE_NAMES:
                    self._on_texture_selected(norm_name)
                else:
                    self.selected_texture_name = os.path.basename(img_k)
                    self.lbl_selected_tex.setText(self.selected_texture_name)
                    self.sample_widget.set_fill(f)
            else:
                self.tab_widget.setCurrentIndex(3)
                img_k = getattr(f, "image_path", "")
                self.selected_picture_path = img_k
                self.lbl_pic_path.setText(os.path.basename(img_k))
                self.chk_tile_pic.setChecked(bool(f.tile))
                self.sample_widget.set_fill(f)
        else:
            self.tab_widget.setCurrentIndex(0)
            self._refresh_gradient()

    def get_fill(self) -> Fill:
        """Return the finalized Fill object configured by the user."""
        curr_tab = self.tab_widget.currentIndex()
        if curr_tab == 0:
            return self._build_gradient_fill_variant(self.selected_variant_idx)
        elif curr_tab == 1:
            norm_k = TEXTURE_KEY_MAP.get(self.selected_texture_name, self.selected_texture_name)
            return Fill.image_fill(image_path=norm_k, tile=True)
        elif curr_tab == 2:
            return Fill.pattern_fill(
                prst=self.selected_pattern_key,
                fg=self.btn_patt_fg.get_color(),
                bg=self.btn_patt_bg.get_color(),
            )
        elif curr_tab == 3:
            return Fill.image_fill(
                image_path=self.selected_picture_path, tile=self.chk_tile_pic.isChecked()
            )
        return self.current_fill


# ==============================================================================
# Main Background Dialog
# ==============================================================================


class BackgroundDialog(QDialog):
    """PowerPoint 2003 Classic Background Formatting Dialog."""

    backgroundApplied = Signal(object, bool)  # (Fill | None, apply_to_all: bool)

    def __init__(
        self,
        slide: Slide,
        presentation: Presentation,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.slide = slide
        self.presentation = presentation

        self.design = presentation.get_design_for_slide(slide)
        self.current_fill: Fill | None = copy.deepcopy(slide.bg) if slide.bg else None
        self.omit_master: bool = bool(slide.hide_master)

        self.setWindowTitle(safe_tr("背景"))
        self.resize(380, 240)
        self.setModal(True)

        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(16)

        # Left Column: Preview & Controls
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)

        self.lbl_bg_fill = QLabel(safe_tr("背景填充"), self)
        self.lbl_bg_fill.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(self.lbl_bg_fill)

        # Miniature Canvas Preview
        self.preview_widget = SlideBackgroundPreview(self.slide, self.presentation, self)
        left_layout.addWidget(self.preview_widget)

        # Color dropdown menu / picker button
        self.btn_fill_picker = QPushButton(safe_tr("颜色与效果(&C)..."), self)
        self.menu_fill = QMenu(self)
        self._populate_fill_menu()
        self.btn_fill_picker.setMenu(self.menu_fill)
        left_layout.addWidget(self.btn_fill_picker)

        # Checkbox: Omit background graphics from master
        self.chk_omit_master = QCheckBox(
            safe_tr("忽略母版的背景图形(&O)"), self
        )
        self.chk_omit_master.setChecked(self.omit_master)
        self.chk_omit_master.toggled.connect(self._on_omit_toggled)
        left_layout.addWidget(self.chk_omit_master)

        left_layout.addStretch()
        root_layout.addLayout(left_layout)

        # Right Column: Action Buttons (Apply to All, Apply, Cancel, Preview)
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_apply_all = QPushButton(safe_tr("全部应用(&A)"), self)
        self.btn_apply_all.clicked.connect(self.apply_to_all_slides)

        self.btn_apply = QPushButton(safe_tr("应用(&P)"), self)
        self.btn_apply.setDefault(True)
        self.btn_apply.clicked.connect(self.apply_to_current_slide)

        self.btn_cancel = QPushButton(safe_tr("取消"), self)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_preview = QPushButton(safe_tr("预览(&V)"), self)
        self.btn_preview.clicked.connect(self._update_preview)

        btn_layout.addWidget(self.btn_apply_all)
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_preview)
        btn_layout.addStretch()

        root_layout.addLayout(btn_layout)

    def _populate_fill_menu(self) -> None:
        self.menu_fill.clear()

        # Automatic (Default from master)
        act_auto = self.menu_fill.addAction(safe_tr("自动 (继承母版)"))
        act_auto.triggered.connect(self._set_auto_fill)
        self.menu_fill.addSeparator()

        # Standard Colors Palette Submenu
        menu_std = self.menu_fill.addMenu(safe_tr("标准颜色"))
        palette = [
            ("#FFFFFF", "白色"),
            ("#000000", "黑色"),
            ("#C00000", "暗红"),
            ("#FF0000", "红色"),
            ("#FFC000", "金色"),
            ("#FFFF00", "黄色"),
            ("#92D050", "浅绿"),
            ("#00B050", "绿色"),
            ("#00B0F0", "浅蓝"),
            ("#0070C0", "蓝色"),
            ("#002060", "深蓝"),
            ("#7030A0", "紫色"),
        ]
        for hex_col, name in palette:
            act = menu_std.addAction(safe_tr(name))
            pix = QPixmap(16, 16)
            pix.fill(QColor(hex_col))
            act.setIcon(QIcon(pix))
            act.triggered.connect(lambda _, c=hex_col: self._set_solid_color(c))

        self.menu_fill.addSeparator()

        # More Colors...
        act_more = self.menu_fill.addAction(safe_tr("其他颜色(&M)..."))
        act_more.triggered.connect(self._choose_more_colors)

        # Fill Effects...
        act_fx = self.menu_fill.addAction(safe_tr("填充效果(&F)..."))
        act_fx.triggered.connect(self._open_fill_effects)

    def _set_auto_fill(self) -> None:
        self.current_fill = None
        self._update_preview()

    def _set_solid_color(self, hex_color: str) -> None:
        self.current_fill = Fill.solid(hex_color)
        self._update_preview()

    def _choose_more_colors(self) -> None:
        initial = (
            QColor(self.current_fill.color)
            if self.current_fill and self.current_fill.type == "solid"
            else QColor("#FFFFFF")
        )
        col = QColorDialog.getColor(initial, self, safe_tr("选择背景颜色"))
        if col.isValid():
            self._set_solid_color(col.name(QColor.NameFormat.HexRgb).upper())

    def _open_fill_effects(self) -> None:
        dlg = FillEffectsDialog(self.current_fill, self.design, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.current_fill = dlg.get_fill()
            self._update_preview()

    def _on_omit_toggled(self, checked: bool) -> None:
        self.omit_master = checked
        self._update_preview()

    def _update_preview(self) -> None:
        self.preview_widget.set_state(self.current_fill, self.omit_master)

    def apply_to_current_slide(self) -> None:
        """Apply the background fill and omit setting to the current slide."""
        self.slide.bg = copy.deepcopy(self.current_fill)
        self.slide.hide_master = self.omit_master
        self.backgroundApplied.emit(self.current_fill, False)
        self.accept()

    def apply_to_all_slides(self) -> None:
        """Apply the background fill and omit setting to all slides in presentation."""
        # 1. Update active design master background
        if self.design:
            if self.current_fill is not None:
                self.design.bg = copy.deepcopy(self.current_fill)

        # 2. Clear individual overrides and update omit on all slides
        for s in self.presentation.slides:
            s.bg = None
            s.hide_master = self.omit_master

        self.backgroundApplied.emit(self.current_fill, True)
        self.accept()

    def get_current_fill(self) -> Fill | None:
        return self.current_fill

    def is_omit_master_graphics(self) -> bool:
        return self.omit_master

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("背景"))
        self.lbl_bg_fill.setText(safe_tr("背景填充"))
        self.btn_fill_picker.setText(safe_tr("颜色与效果(&C)..."))
        self.chk_omit_master.setText(safe_tr("忽略母版的背景图形(&O)"))
        self.btn_apply_all.setText(safe_tr("全部应用(&A)"))
        self.btn_apply.setText(safe_tr("应用(&P)"))
        self.btn_cancel.setText(safe_tr("取消"))
        self.btn_preview.setText(safe_tr("预览(&V)"))
        self._populate_fill_menu()
