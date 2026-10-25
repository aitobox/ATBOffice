"""Font tab for FormatCellsDialog."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    return QCoreApplication.translate("FontTab", text)


COMMON_FONTS = [
    "Arial",
    "Calibri",
    "Courier New",
    "Microsoft YaHei",
    "PingFang SC",
    "Segoe UI",
    "SimHei",
    "SimSun",
    "Tahoma",
    "Times New Roman",
    "Verdana",
]

FONT_STYLES = [
    ("r", "常规"),
    ("i", "倾斜"),
    ("b", "加粗"),
    ("bi", "加粗 倾斜"),
]

FONT_SIZES = [
    "8",
    "9",
    "10",
    "11",
    "12",
    "14",
    "16",
    "18",
    "20",
    "22",
    "24",
    "26",
    "28",
    "36",
    "48",
    "72",
]

UNDERLINES = [
    ("none", "无"),
    ("single", "单下划线"),
    ("double", "双下划线"),
    ("singleAccounting", "会计用单下划线"),
    ("doubleAccounting", "会计用双下划线"),
]


class FontTab(QWidget):
    """Tab 3: Font styling and attributes."""

    def __init__(
        self,
        font_family: str = "Arial",
        font_size: int = 10,
        bold: bool = False,
        italic: bool = False,
        underline_style: str = "none",
        strike: bool = False,
        vert_align: str | None = None,
        fg_color: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fg_color = fg_color or "#000000"

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. Top Section: 3 Columns (Font Family, Style, Size)
        col_layout = QHBoxLayout()
        col_layout.setSpacing(10)

        # Font Family
        fam_layout = QVBoxLayout()
        self.lbl_family = QLabel(safe_tr("字体(&F):"))
        self.edit_family = QLineEdit(font_family)
        self.list_family = QListWidget()
        self.list_family.addItems(COMMON_FONTS)
        fam_layout.addWidget(self.lbl_family)
        fam_layout.addWidget(self.edit_family)
        fam_layout.addWidget(self.list_family)
        col_layout.addLayout(fam_layout, 2)

        # Font Style
        style_layout = QVBoxLayout()
        self.lbl_style = QLabel(safe_tr("字形(&O):"))
        self.list_style = QListWidget()
        for key, name in FONT_STYLES:
            self.list_style.addItem(safe_tr(name))
        style_layout.addWidget(self.lbl_style)
        style_layout.addWidget(self.list_style)
        col_layout.addLayout(style_layout, 1)

        # Font Size
        size_layout = QVBoxLayout()
        self.lbl_size = QLabel(safe_tr("字号(&S):"))
        self.edit_size = QLineEdit(str(font_size))
        self.list_size = QListWidget()
        self.list_size.addItems(FONT_SIZES)
        size_layout.addWidget(self.lbl_size)
        size_layout.addWidget(self.edit_size)
        size_layout.addWidget(self.list_size)
        col_layout.addLayout(size_layout, 1)

        main_layout.addLayout(col_layout)

        # 2. Middle Row: Underline, Color, Normal Font
        mid_layout = QHBoxLayout()
        mid_layout.setSpacing(16)

        u_form = QFormLayout()
        self.lbl_underline = QLabel(safe_tr("下划线(&U):"))
        self.combo_underline = QComboBox()
        for key, name in UNDERLINES:
            self.combo_underline.addItem(safe_tr(name), key)
        u_form.addRow(self.lbl_underline, self.combo_underline)
        mid_layout.addLayout(u_form)

        c_form = QFormLayout()
        self.lbl_color = QLabel(safe_tr("颜色(&C):"))
        self.btn_color = QPushButton(safe_tr("自动"))
        self.btn_color.setFixedWidth(80)
        self.btn_color.clicked.connect(self._choose_color)
        c_form.addRow(self.lbl_color, self.btn_color)
        mid_layout.addLayout(c_form)

        self.btn_normal_font = QPushButton(safe_tr("常规字体(&N)"))
        self.btn_normal_font.clicked.connect(self._reset_to_normal)
        mid_layout.addWidget(self.btn_normal_font)
        mid_layout.addStretch(1)

        main_layout.addLayout(mid_layout)

        # 3. Bottom Row: Effects + Preview
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(16)

        # Effects
        self.grp_effects = QGroupBox(safe_tr("特殊效果"))
        eff_layout = QVBoxLayout(self.grp_effects)
        self.check_strike = QCheckBox(safe_tr("删除线(&K)"))
        self.check_strike.setChecked(strike)
        self.check_super = QCheckBox(safe_tr("上标(&E)"))
        self.check_super.setChecked(vert_align == "superscript")
        self.check_sub = QCheckBox(safe_tr("下标(&B)"))
        self.check_sub.setChecked(vert_align == "subscript")

        self.check_super.toggled.connect(
            lambda c: self.check_sub.setChecked(False) if c else None
        )
        self.check_sub.toggled.connect(
            lambda c: self.check_super.setChecked(False) if c else None
        )

        eff_layout.addWidget(self.check_strike)
        eff_layout.addWidget(self.check_super)
        eff_layout.addWidget(self.check_sub)
        bottom_layout.addWidget(self.grp_effects, 1)

        # Preview
        self.grp_preview = QGroupBox(safe_tr("预览"))
        prev_layout = QVBoxLayout(self.grp_preview)
        self.font_preview = QLabel("AaBbCcYyZz 123 预览文本")
        self.font_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.font_preview.setFixedHeight(70)
        self.font_preview.setStyleSheet(
            "background: #FFFFFF; border: 1px solid #C0C0C0;"
        )
        prev_layout.addWidget(self.font_preview)
        bottom_layout.addWidget(self.grp_preview, 2)

        main_layout.addLayout(bottom_layout)

        # Signals
        self.list_family.itemClicked.connect(
            lambda item: self.edit_family.setText(item.text())
        )
        self.edit_family.textChanged.connect(self._on_family_changed)

        self.list_style.currentRowChanged.connect(
            lambda _: self.update_preview()
        )

        self.list_size.itemClicked.connect(
            lambda item: self.edit_size.setText(item.text())
        )
        self.edit_size.textChanged.connect(self._on_size_changed)

        self.combo_underline.currentIndexChanged.connect(
            lambda _: self.update_preview()
        )
        self.check_strike.toggled.connect(lambda _: self.update_preview())
        self.check_super.toggled.connect(lambda _: self.update_preview())
        self.check_sub.toggled.connect(lambda _: self.update_preview())

        # Set initial values
        self.set_font_family(font_family)
        self.set_font_size(font_size)
        self.set_bold(bold)
        self.set_italic(italic)
        self._set_underline(underline_style)
        self._update_color_button()
        self.update_preview()

    def _choose_color(self) -> None:
        col = QColorDialog.getColor(QColor(self._fg_color), self)
        if col.isValid():
            self._fg_color = col.name()
            self._update_color_button()
            self.update_preview()

    def _update_color_button(self) -> None:
        if self._fg_color and self._fg_color.lower() != "#000000":
            self.btn_color.setText("")
            self.btn_color.setStyleSheet(
                f"background-color: {self._fg_color}; border: 1px solid #888;"
            )
        else:
            self.btn_color.setText(safe_tr("自动"))
            self.btn_color.setStyleSheet("")

    def _reset_to_normal(self) -> None:
        self.set_font_family("Arial")
        self.set_font_size(10)
        self.set_bold(False)
        self.set_italic(False)
        self.combo_underline.setCurrentIndex(0)
        self.check_strike.setChecked(False)
        self.check_super.setChecked(False)
        self.check_sub.setChecked(False)
        self._fg_color = "#000000"
        self._update_color_button()
        self.update_preview()

    def set_font_family(self, family: str) -> None:
        self.edit_family.setText(family)
        items = self.list_family.findItems(family, Qt.MatchFlag.MatchExactly)
        if items:
            self.list_family.setCurrentItem(items[0])

    def set_font_size(self, size: int) -> None:
        self.edit_size.setText(str(size))
        items = self.list_size.findItems(str(size), Qt.MatchFlag.MatchExactly)
        if items:
            self.list_size.setCurrentItem(items[0])

    def set_bold(self, bold: bool) -> None:
        is_i = self.is_italic()
        if bold and is_i:
            self.list_style.setCurrentRow(3)
        elif bold:
            self.list_style.setCurrentRow(2)
        elif is_i:
            self.list_style.setCurrentRow(1)
        else:
            self.list_style.setCurrentRow(0)
        self.update_preview()

    def set_italic(self, italic: bool) -> None:
        is_b = self.is_bold()
        if is_b and italic:
            self.list_style.setCurrentRow(3)
        elif is_b:
            self.list_style.setCurrentRow(2)
        elif italic:
            self.list_style.setCurrentRow(1)
        else:
            self.list_style.setCurrentRow(0)
        self.update_preview()

    def _set_underline(self, u_style: str) -> None:
        for i in range(self.combo_underline.count()):
            if self.combo_underline.itemData(i) == u_style:
                self.combo_underline.setCurrentIndex(i)
                break

    def is_bold(self) -> bool:
        r = self.list_style.currentRow()
        return r in (2, 3)

    def is_italic(self) -> bool:
        r = self.list_style.currentRow()
        return r in (1, 3)

    def _on_family_changed(self, text: str) -> None:
        items = self.list_family.findItems(text, Qt.MatchFlag.MatchExactly)
        if items:
            self.list_family.setCurrentItem(items[0])
        self.update_preview()

    def _on_size_changed(self, text: str) -> None:
        items = self.list_size.findItems(text, Qt.MatchFlag.MatchExactly)
        if items:
            self.list_size.setCurrentItem(items[0])
        self.update_preview()

    def update_preview(self) -> None:
        fam = self.edit_family.text().strip() or "Arial"
        try:
            sz = int(self.edit_size.text())
        except ValueError:
            sz = 10

        font = QFont(fam, max(8, min(72, sz)))
        font.setBold(self.is_bold())
        font.setItalic(self.is_italic())
        u_style = self.combo_underline.currentData() or "none"
        font.setUnderline(u_style != "none")
        font.setStrikeOut(self.check_strike.isChecked())
        self.font_preview.setFont(font)

        col = self._fg_color if self._fg_color else "#000000"
        self.font_preview.setStyleSheet(
            f"background: #FFFFFF; border: 1px solid #C0C0C0; color: {col};"
        )

    def get_font(self) -> dict[str, Any]:
        try:
            sz = int(self.edit_size.text())
        except ValueError:
            sz = 10

        u_data = self.combo_underline.currentData() or "none"
        vert = None
        if self.check_super.isChecked():
            vert = "superscript"
        elif self.check_sub.isChecked():
            vert = "subscript"

        return {
            "font_family": self.edit_family.text().strip() or "Arial",
            "font_size": sz,
            "bold": self.is_bold(),
            "italic": self.is_italic(),
            "underline_style": u_data,
            "strike": self.check_strike.isChecked(),
            "vert_align": vert,
            "fg_color": self._fg_color,
        }

    def retranslate_ui(self) -> None:
        self.lbl_family.setText(safe_tr("字体(&F):"))
        self.lbl_style.setText(safe_tr("字形(&O):"))
        self.lbl_size.setText(safe_tr("字号(&S):"))
        self.lbl_underline.setText(safe_tr("下划线(&U):"))
        self.lbl_color.setText(safe_tr("颜色(&C):"))
        self.btn_normal_font.setText(safe_tr("常规字体(&N)"))
        self.grp_effects.setTitle(safe_tr("特殊效果"))
        self.check_strike.setText(safe_tr("删除线(&K)"))
        self.check_super.setText(safe_tr("上标(&E)"))
        self.check_sub.setText(safe_tr("下标(&B)"))
        self.grp_preview.setTitle(safe_tr("预览"))
        self.update_preview()
