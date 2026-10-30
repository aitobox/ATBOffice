"""Classic Borders and Shading Dialog for Quire Writer."""

from __future__ import annotations

import copy

from PySide6.QtCore import QCoreApplication, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.models.properties import (
    BorderProperties,
    ShadingProperties,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("BordersShadingDialog", text)


BORDER_STYLE_NAMES: list[tuple[str, str]] = [
    ("single", safe_tr("单实线")),
    ("dotted", safe_tr("点线")),
    ("dashSmallGap", safe_tr("短虚线")),
    ("dashed", safe_tr("虚线")),
    ("dotDash", safe_tr("点划线")),
    ("dotDotDash", safe_tr("双点划线")),
    ("double", safe_tr("双实线")),
    ("triple", safe_tr("三实线")),
    ("thinThickSmallGap", safe_tr("细粗线")),
    ("thickThinSmallGap", safe_tr("粗细线")),
    ("thinThickThinSmallGap", safe_tr("细粗细线")),
    ("wave", safe_tr("波浪线")),
    ("doubleWave", safe_tr("双波浪线")),
]

BORDER_WIDTHS: list[float] = [0.25, 0.5, 0.75, 1.0, 1.5, 2.25, 3.0, 4.5, 6.0]

SHD_PATTERNS: list[tuple[str, str]] = [
    ("clear", safe_tr("清除")),
    ("solid", safe_tr("纯色 (100%)")),
    ("pct5", "5%"),
    ("pct10", "10%"),
    ("pct15", "15%"),
    ("pct20", "20%"),
    ("pct25", "25%"),
    ("pct30", "30%"),
    ("pct40", "40%"),
    ("pct50", "50%"),
    ("pct60", "60%"),
    ("pct70", "70%"),
    ("pct75", "75%"),
    ("pct80", "80%"),
    ("pct90", "90%"),
    ("horzStripe", safe_tr("深色水平线")),
    ("vertStripe", safe_tr("深色垂直线")),
    ("diagCross", safe_tr("对角网格")),
]


class BorderPreviewWidget(QWidget):
    """Interactive preview canvas showing active borders with clickable toggles."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(140, 140)
        self.borders: dict[str, BorderProperties | None] = {
            "top": None,
            "bottom": None,
            "left": None,
            "right": None,
            "insideH": None,
            "insideV": None,
        }

    def set_borders(self, borders: dict[str, BorderProperties | None]) -> None:
        self.borders = copy.deepcopy(borders)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor("#FAFAFA"))
        painter.setPen(QPen(QColor("#D0D0D0"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        box_rect = QRect(25, 25, 90, 90)

        # Inner text simulation lines (gray)
        painter.setPen(QPen(QColor("#E0E0E0"), 2))
        painter.drawLine(35, 45, 105, 45)
        painter.drawLine(35, 55, 90, 55)
        painter.drawLine(35, 80, 105, 80)
        painter.drawLine(35, 90, 90, 90)

        # Draw active borders
        for side, bd in self.borders.items():
            if not bd or bd.val in ("none", "nil"):
                continue

            # Pen setup
            c = QColor("#000000") if bd.color == "auto" else QColor(f"#{bd.color.lstrip('#')}")
            w = max(1, int(bd.sz))
            style = Qt.PenStyle.SolidLine
            if bd.val == "dotted":
                style = Qt.PenStyle.DotLine
            elif bd.val in ("dashed", "dashSmallGap"):
                style = Qt.PenStyle.DashLine
            elif bd.val == "dotDash":
                style = Qt.PenStyle.DashDotLine

            painter.setPen(QPen(c, w, style))

            if side == "top":
                painter.drawLine(box_rect.topLeft(), box_rect.topRight())
            elif side == "bottom":
                painter.drawLine(box_rect.bottomLeft(), box_rect.bottomRight())
            elif side == "left":
                painter.drawLine(box_rect.topLeft(), box_rect.bottomLeft())
            elif side == "right":
                painter.drawLine(box_rect.topRight(), box_rect.bottomRight())
            elif side == "insideH":
                painter.drawLine(
                    box_rect.left(), box_rect.center().y(), box_rect.right(), box_rect.center().y()
                )
            elif side == "insideV":
                painter.drawLine(
                    box_rect.center().x(), box_rect.top(), box_rect.center().x(), box_rect.bottom()
                )


class ShadingPreviewWidget(QWidget):
    """Preview box for fill color and patterns."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(140, 90)
        self.fill_color: str | None = None
        self.pattern: str = "clear"
        self.pattern_color: str = "auto"

    def set_shading(self, fill: str | None, pattern: str, p_color: str) -> None:
        self.fill_color = fill
        self.pattern = pattern
        self.pattern_color = p_color
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background base
        bg_col = QColor(f"#{self.fill_color.lstrip('#')}") if self.fill_color else QColor("#FFFFFF")
        painter.fillRect(self.rect(), bg_col)
        painter.setPen(QPen(QColor("#B0B0B0"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        # Pattern simulation
        if self.pattern and self.pattern != "clear":
            pat_col = (
                QColor("#000000")
                if self.pattern_color == "auto"
                else QColor(f"#{self.pattern_color.lstrip('#')}")
            )
            painter.setPen(QPen(pat_col, 1, Qt.PenStyle.DotLine))
            for y in range(4, self.height(), 8):
                painter.drawLine(4, y, self.width() - 4, y)


class BordersShadingDialog(QDialog):
    """Word 2003 classic Borders and Shading modal dialog."""

    def __init__(
        self,
        parent: QWidget | None = None,
        borders: dict[str, BorderProperties] | None = None,
        shading: ShadingProperties | None = None,
        target_type: str = "table",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("边框和底纹"))
        self.setModal(True)
        self.setMinimumWidth(520)

        self._target_type = target_type
        self._current_pen = BorderProperties(val="single", sz=0.5, color="auto")
        self._borders: dict[str, BorderProperties | None] = {
            "top": None,
            "bottom": None,
            "left": None,
            "right": None,
            "insideH": None,
            "insideV": None,
        }
        if borders:
            for k, v in borders.items():
                if k in self._borders and v and v.val not in ("none", "nil"):
                    self._borders[k] = BorderProperties(val=v.val, sz=v.sz, color=v.color)

        self._fill_color: str | None = shading.fill if shading and shading.fill != "auto" else None
        self._shading_pattern: str = shading.val if shading else "clear"
        self._shading_pcolor: str = shading.color if shading else "auto"

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        self.tab_widget = QTabWidget(self)

        # Tab 1: Borders
        self.tab_borders = QWidget()
        self._init_borders_tab()
        self.tab_widget.addTab(self.tab_borders, safe_tr("边框"))

        # Tab 2: Page Border
        self.tab_page = QWidget()
        self._init_page_tab()
        self.tab_widget.addTab(self.tab_page, safe_tr("页面边框"))

        # Tab 3: Shading
        self.tab_shading = QWidget()
        self._init_shading_tab()
        self.tab_widget.addTab(self.tab_shading, safe_tr("底纹"))

        main_layout.addWidget(self.tab_widget)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.retranslate_ui()
        self._update_preview()

    def _init_borders_tab(self) -> None:
        layout = QHBoxLayout(self.tab_borders)
        layout.setSpacing(10)

        # Presets (Setting)
        self.group_setting = QGroupBox(self.tab_borders)
        v_preset = QVBoxLayout(self.group_setting)
        self.preset_none = QPushButton(self.group_setting)
        self.preset_box = QPushButton(self.group_setting)
        self.preset_all = QPushButton(self.group_setting)
        self.preset_grid = QPushButton(self.group_setting)
        self.preset_custom = QPushButton(self.group_setting)

        self.preset_none.clicked.connect(lambda: self._apply_preset("none"))
        self.preset_box.clicked.connect(lambda: self._apply_preset("box"))
        self.preset_all.clicked.connect(lambda: self._apply_preset("all"))
        self.preset_grid.clicked.connect(lambda: self._apply_preset("grid"))
        self.preset_custom.clicked.connect(lambda: self._apply_preset("custom"))

        for b in [
            self.preset_none,
            self.preset_box,
            self.preset_all,
            self.preset_grid,
            self.preset_custom,
        ]:
            v_preset.addWidget(b)
        v_preset.addStretch(1)
        layout.addWidget(self.group_setting)

        # Style & Pen Settings
        col_style = QVBoxLayout()
        self.label_style = QLabel(self.tab_borders)
        self.list_styles = QListWidget(self.tab_borders)
        for val, name in BORDER_STYLE_NAMES:
            self.list_styles.addItem(name)
        self.list_styles.setCurrentRow(0)
        self.list_styles.currentRowChanged.connect(self._on_style_changed)

        self.label_color = QLabel(self.tab_borders)
        self.combo_color = QComboBox(self.tab_borders)
        for c_name, c_val in [
            ("自动", "auto"),
            ("黑色", "000000"),
            ("蓝色", "0000FF"),
            ("红色", "FF0000"),
            ("绿色", "008000"),
        ]:
            self.combo_color.addItem(c_name, c_val)
        self.combo_color.currentIndexChanged.connect(self._on_color_changed)

        self.label_width = QLabel(self.tab_borders)
        self.combo_width = QComboBox(self.tab_borders)
        for w in BORDER_WIDTHS:
            self.combo_width.addItem(f"{w:g} pt", w)
        self.combo_width.setCurrentIndex(1)  # 0.5 pt
        self.combo_width.currentIndexChanged.connect(self._on_width_changed)

        col_style.addWidget(self.label_style)
        col_style.addWidget(self.list_styles)
        col_style.addWidget(self.label_color)
        col_style.addWidget(self.combo_color)
        col_style.addWidget(self.label_width)
        col_style.addWidget(self.combo_width)
        layout.addLayout(col_style)

        # Preview & Apply To
        col_pv = QVBoxLayout()
        self.label_pv = QLabel(safe_tr("预览"), self.tab_borders)
        self.pv_border = BorderPreviewWidget(self.tab_borders)

        # Toggle buttons row
        row_toggles = QGridLayout()
        self.btn_top = QPushButton("上", self.tab_borders)
        self.btn_bottom = QPushButton("下", self.tab_borders)
        self.btn_left = QPushButton("左", self.tab_borders)
        self.btn_right = QPushButton("右", self.tab_borders)
        self.btn_inside_h = QPushButton("横", self.tab_borders)
        self.btn_inside_v = QPushButton("竖", self.tab_borders)

        self.btn_top.clicked.connect(lambda: self._toggle_side("top"))
        self.btn_bottom.clicked.connect(lambda: self._toggle_side("bottom"))
        self.btn_left.clicked.connect(lambda: self._toggle_side("left"))
        self.btn_right.clicked.connect(lambda: self._toggle_side("right"))
        self.btn_inside_h.clicked.connect(lambda: self._toggle_side("insideH"))
        self.btn_inside_v.clicked.connect(lambda: self._toggle_side("insideV"))

        row_toggles.addWidget(self.btn_top, 0, 1)
        row_toggles.addWidget(self.btn_left, 1, 0)
        row_toggles.addWidget(self.btn_right, 1, 2)
        row_toggles.addWidget(self.btn_bottom, 2, 1)
        row_toggles.addWidget(self.btn_inside_h, 1, 1)
        row_toggles.addWidget(self.btn_inside_v, 2, 0)

        self.label_apply = QLabel(self.tab_borders)
        self.combo_apply = QComboBox(self.tab_borders)
        for app_name, app_val in [
            ("表格", "table"),
            ("单元格", "cell"),
            ("段落", "para"),
            ("文字", "text"),
        ]:
            self.combo_apply.addItem(app_name, app_val)
        if self._target_type == "cell":
            self.combo_apply.setCurrentIndex(1)
        elif self._target_type == "para":
            self.combo_apply.setCurrentIndex(2)
        elif self._target_type == "text":
            self.combo_apply.setCurrentIndex(3)

        col_pv.addWidget(self.label_pv)
        col_pv.addWidget(self.pv_border)
        col_pv.addLayout(row_toggles)
        col_pv.addWidget(self.label_apply)
        col_pv.addWidget(self.combo_apply)
        layout.addLayout(col_pv)

    def _init_page_tab(self) -> None:
        layout = QVBoxLayout(self.tab_page)
        self.label_page_note = QLabel(
            safe_tr("页面边框选项将应用于节边界或整篇文档。"), self.tab_page
        )
        self.label_page_apply = QLabel(safe_tr("应用于(&A):"), self.tab_page)
        self.combo_page_apply = QComboBox(self.tab_page)
        for item_name, item_val in [
            ("整篇文档", "all"),
            ("本节", "section"),
            ("本节 - 仅首页", "firstPage"),
            ("本节 - 除首页外所有页", "notFirstPage"),
        ]:
            self.combo_page_apply.addItem(item_name, item_val)

        layout.addWidget(self.label_page_note)
        layout.addWidget(self.label_page_apply)
        layout.addWidget(self.combo_page_apply)
        layout.addStretch(1)

    def _init_shading_tab(self) -> None:
        layout = QHBoxLayout(self.tab_shading)
        layout.setSpacing(12)

        # Left: Fill section
        col_fill = QVBoxLayout()
        self.label_fill = QLabel(safe_tr("填充(&F)"), self.tab_shading)
        self.btn_no_fill = QPushButton(safe_tr("无颜色"), self.tab_shading)
        self.btn_no_fill.clicked.connect(lambda: self.set_fill_color(None))

        # Swatch palette
        grid_swatches = QGridLayout()
        standard_colors = [
            "#FFFFFF",
            "#000000",
            "#EEECE1",
            "#1F497D",
            "#4F81BD",
            "#C00000",
            "#9BBB59",
            "#8064A2",
            "#F2F2F2",
            "#7F7F7F",
            "#DDD9C3",
            "#C6D9F0",
            "#DBE5F1",
            "#F2DCDB",
            "#EAF1DD",
            "#FFE082",
        ]
        for idx, col in enumerate(standard_colors):
            btn = QPushButton(self.tab_shading)
            btn.setFixedSize(20, 20)
            btn.setStyleSheet(f"background-color: {col}; border: 1px solid #999;")
            btn.clicked.connect(lambda _, c=col: self.set_fill_color(c))
            grid_swatches.addWidget(btn, idx // 8, idx % 8)

        self.label_cur_color = QLabel(self.tab_shading)
        self.btn_more_colors = QPushButton(safe_tr("其他颜色(&M)..."), self.tab_shading)
        self.btn_more_colors.clicked.connect(self._choose_more_colors)

        col_fill.addWidget(self.label_fill)
        col_fill.addWidget(self.btn_no_fill)
        col_fill.addLayout(grid_swatches)
        col_fill.addWidget(self.label_cur_color)
        col_fill.addWidget(self.btn_more_colors)
        col_fill.addStretch(1)
        layout.addLayout(col_fill)

        # Right: Patterns & Preview
        col_pat = QVBoxLayout()
        self.label_pat_style = QLabel(safe_tr("样式(&S):"), self.tab_shading)
        self.combo_pattern = QComboBox(self.tab_shading)
        for p_code, p_label in SHD_PATTERNS:
            self.combo_pattern.addItem(p_label, p_code)
        self.combo_pattern.currentIndexChanged.connect(self._on_pattern_changed)

        self.label_pat_color = QLabel(safe_tr("颜色(&C):"), self.tab_shading)
        self.combo_pat_color = QComboBox(self.tab_shading)
        for c_name, c_val in [
            ("自动", "auto"),
            ("黑色", "000000"),
            ("灰色", "808080"),
            ("蓝色", "0000FF"),
        ]:
            self.combo_pat_color.addItem(c_name, c_val)
        self.combo_pat_color.currentIndexChanged.connect(self._on_pattern_color_changed)

        self.label_shd_pv = QLabel(safe_tr("预览"), self.tab_shading)
        self.pv_shd = ShadingPreviewWidget(self.tab_shading)

        col_pat.addWidget(self.label_pat_style)
        col_pat.addWidget(self.combo_pattern)
        col_pat.addWidget(self.label_pat_color)
        col_pat.addWidget(self.combo_pat_color)
        col_pat.addWidget(self.label_shd_pv)
        col_pat.addWidget(self.pv_shd)
        col_pat.addStretch(1)
        layout.addLayout(col_pat)

    def set_fill_color(self, hex_color: str | None) -> None:
        self._fill_color = hex_color.lstrip("#") if hex_color else None
        name = safe_tr("无颜色") if not self._fill_color else f"#{self._fill_color}"
        self.label_cur_color.setText(safe_tr("当前颜色: ") + name)
        self._update_preview()

    def _choose_more_colors(self) -> None:
        initial = QColor(f"#{self._fill_color}") if self._fill_color else QColor("#FFFFFF")
        color = QColorDialog.getColor(initial, self, safe_tr("选择颜色"))
        if color.isValid():
            self.set_fill_color(color.name().upper())

    def _on_style_changed(self, row: int) -> None:
        if 0 <= row < len(BORDER_STYLE_NAMES):
            self._current_pen.val = BORDER_STYLE_NAMES[row][0]

    def _on_color_changed(self) -> None:
        self._current_pen.color = str(self.combo_color.currentData())

    def _on_width_changed(self) -> None:
        self._current_pen.sz = float(self.combo_width.currentData())

    def _on_pattern_changed(self) -> None:
        self._shading_pattern = str(self.combo_pattern.currentData())
        self._update_preview()

    def _on_pattern_color_changed(self) -> None:
        self._shading_pcolor = str(self.combo_pat_color.currentData())
        self._update_preview()

    def _apply_preset(self, preset: str) -> None:
        for k in self._borders:
            self._borders[k] = None

        if preset == "none":
            pass
        elif preset == "box":
            for s in ["top", "bottom", "left", "right"]:
                self._borders[s] = copy.deepcopy(self._current_pen)
        elif preset in ("all", "custom"):
            for s in self._borders:
                self._borders[s] = copy.deepcopy(self._current_pen)
        elif preset == "grid":
            outer_pen = copy.deepcopy(self._current_pen)
            outer_pen.sz = max(1.5, outer_pen.sz)
            for s in ["top", "bottom", "left", "right"]:
                self._borders[s] = outer_pen
            for s in ["insideH", "insideV"]:
                self._borders[s] = BorderProperties(
                    val=self._current_pen.val, sz=0.5, color=self._current_pen.color
                )

        self._update_preview()

    def _toggle_side(self, side: str) -> None:
        if self._borders.get(side):
            self._borders[side] = None
        else:
            self._borders[side] = copy.deepcopy(self._current_pen)
        self._update_preview()

    def _update_preview(self) -> None:
        self.pv_border.set_borders(self._borders)
        self.pv_shd.set_shading(self._fill_color, self._shading_pattern, self._shading_pcolor)

    def retranslate_ui(self) -> None:
        """Update all translatable strings dynamically."""
        self.setWindowTitle(safe_tr("边框和底纹"))
        self.tab_widget.setTabText(0, safe_tr("边框"))
        self.tab_widget.setTabText(1, safe_tr("页面边框"))
        self.tab_widget.setTabText(2, safe_tr("底纹"))

        self.group_setting.setTitle(safe_tr("设置(&S):"))
        self.preset_none.setText(safe_tr("无(&N)"))
        self.preset_box.setText(safe_tr("方框(&B)"))
        self.preset_all.setText(safe_tr("全部(&A)"))
        self.preset_grid.setText(safe_tr("网格(&G)"))
        self.preset_custom.setText(safe_tr("自定义(&C)"))

        self.label_style.setText(safe_tr("线型(&Y):"))
        self.label_color.setText(safe_tr("颜色(&C):"))
        self.label_width.setText(safe_tr("宽度(&W):"))
        self.label_apply.setText(safe_tr("应用于(&P):"))

        ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(safe_tr("确定"))
        cancel_btn = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(safe_tr("取消"))

    def get_properties(self) -> dict:
        """Return dict with resolved borders and shading properties."""
        bds = {k: v for k, v in self._borders.items() if v and v.val not in ("none", "nil")}
        shd = ShadingProperties(
            val=self._shading_pattern,
            color=self._shading_pcolor,
            fill=self._fill_color if self._fill_color else "auto",
        )
        return {
            "borders": bds,
            "shading": shd,
            "apply_to": self.combo_apply.currentData(),
            "page_apply_to": self.combo_page_apply.currentData(),
        }
