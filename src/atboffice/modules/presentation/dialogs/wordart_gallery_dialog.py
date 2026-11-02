"""PowerPoint 2003 LettersArt (WordArt) Gallery and Text Editor Dialogs for Lectern."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely for WordArtGalleryDialog."""
    return QCoreApplication.translate("WordArtGalleryDialog", text)


WORDART_30_STYLES: list[dict[str, Any]] = [
    # Row 1
    {"name": "Style 1", "fill": "#000000", "stroke": None, "grad": None, "warp": "plain"},
    {"name": "Style 2", "fill": "#FFFFFF", "stroke": "#000000", "grad": None, "warp": "plain"},
    {"name": "Style 3", "fill": None, "stroke": None, "grad": ("#3366FF", "#99CCFF"), "warp": "plain"},
    {"name": "Style 4", "fill": "#C0C0C0", "stroke": "#404040", "grad": None, "warp": "plain", "shadow": True},
    {"name": "Style 5", "fill": None, "stroke": "#993300", "grad": ("#FF6600", "#FFCC00"), "warp": "arch_up"},
    {"name": "Style 6", "fill": "#3366CC", "stroke": None, "grad": None, "warp": "wave1", "shadow": True},
    # Row 2
    {"name": "Style 7", "fill": None, "stroke": "#000000", "grad": ("#FFFFFF", "#808080"), "warp": "plain", "shadow": True},
    {"name": "Style 8", "fill": "#CC0000", "stroke": "#660000", "grad": None, "warp": "slant_up"},
    {"name": "Style 9", "fill": None, "stroke": None, "grad": ("#00CC99", "#006666"), "warp": "plain", "shadow": True},
    {"name": "Style 10", "fill": "#FFFF00", "stroke": "#FF6600", "grad": None, "warp": "plain", "shadow": True},
    {"name": "Style 11", "fill": None, "stroke": None, "grad": ("#CC99FF", "#660099"), "warp": "arch_down"},
    {"name": "Style 12", "fill": "#006600", "stroke": "#003300", "grad": None, "warp": "triangle"},
    # Row 3
    {"name": "Style 13", "fill": None, "stroke": "#663300", "grad": ("#FFCC00", "#CC6600"), "warp": "plain", "shadow": True},
    {"name": "Style 14", "fill": "#000080", "stroke": None, "grad": None, "warp": "chevron", "shadow": True},
    {"name": "Style 15", "fill": None, "stroke": "#000000", "grad": ("#E6E6E6", "#333333"), "warp": "plain"},
    {"name": "Style 16", "fill": "#FF99CC", "stroke": "#CC0066", "grad": None, "warp": "wave1", "shadow": True},
    {"name": "Style 17", "fill": None, "stroke": None, "grad": ("#66CCFF", "#003399"), "warp": "can_up", "shadow": True},
    {"name": "Style 18", "fill": "#996633", "stroke": "#663300", "grad": None, "warp": "slant_down"},
    # Row 4
    {"name": "Style 19", "fill": None, "stroke": "#996600", "grad": ("#FFFF99", "#FF9900"), "warp": "arch_up", "shadow": True},
    {"name": "Style 20", "fill": "#00CCFF", "stroke": "#006699", "grad": None, "warp": "plain"},
    {"name": "Style 21", "fill": None, "stroke": None, "grad": ("#FF0000", "#660000"), "warp": "plain", "shadow": True},
    {"name": "Style 22", "fill": "#808080", "stroke": None, "grad": None, "warp": "plain", "shadow": True},
    {"name": "Style 23", "fill": None, "stroke": "#006600", "grad": ("#99FF99", "#009900"), "warp": "circle"},
    {"name": "Style 24", "fill": "#FF6600", "stroke": None, "grad": None, "warp": "triangle", "shadow": True},
    # Row 5
    {"name": "Style 25", "fill": None, "stroke": None, "grad": ("#000000", "#808080"), "warp": "plain", "shadow": True},
    {"name": "Style 26", "fill": "#FFFFFF", "stroke": "#3366CC", "grad": None, "warp": "arch_up", "shadow": True},
    {"name": "Style 27", "fill": None, "stroke": None, "grad": ("#CC66FF", "#3399FF"), "warp": "wave1"},
    {"name": "Style 28", "fill": "#003366", "stroke": "#99CCFF", "grad": None, "warp": "slant_up", "shadow": True},
    {"name": "Style 29", "fill": None, "stroke": "#990033", "grad": ("#FFCCCC", "#FF3366"), "warp": "chevron"},
    {"name": "Style 30", "fill": "#669900", "stroke": None, "grad": None, "warp": "can_up", "shadow": True},
]


class WordArtGalleryDialog(QDialog):
    """30-style WordArt Style Gallery selection grid."""

    def __init__(
        self,
        current_index: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.selected_style_index: int = max(0, min(29, current_index))
        self.style_buttons: list[QPushButton] = []
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("艺术字库"))
        self.resize(520, 360)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        self.lbl_title = QLabel(safe_tr("选择艺术字样式:"), self)
        self.lbl_title.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        main_layout.addWidget(self.lbl_title)

        # 5x6 Grid of WordArt style cards
        self.grid_container = QWidget(self)
        self.grid_container.setStyleSheet("background-color: #FFFFFF; border: 1px solid #7B9EBD;")
        grid_layout = QGridLayout(self.grid_container)
        grid_layout.setContentsMargins(6, 6, 6, 6)
        grid_layout.setSpacing(4)

        for i, style in enumerate(WORDART_30_STYLES):
            btn = QPushButton(self.grid_container)
            btn.setFixedSize(76, 48)
            btn.setIcon(self._create_style_icon(style, i + 1))
            btn.setIconSize(QSize(72, 44))
            btn.setCheckable(True)
            btn.setChecked(i == self.selected_style_index)
            btn.setStyleSheet(
                """
                QPushButton {
                    border: 1px solid #D0D0D0;
                    background-color: #FFFFFF;
                }
                QPushButton:hover {
                    border: 1px solid #0A246A;
                    background-color: #E5EEF8;
                }
                QPushButton:checked {
                    border: 2px solid #0A246A;
                    background-color: #B6BDD2;
                }
                """
            )
            btn.clicked.connect(lambda ch=False, idx=i: self._select_style(idx))
            self.style_buttons.append(btn)
            grid_layout.addWidget(btn, i // 6, i % 6)

        main_layout.addWidget(self.grid_container, 1)

        # OK / Cancel Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def _create_style_icon(self, style: dict[str, Any], number: int) -> QIcon:
        pix = QPixmap(72, 44)
        pix.fill(QColor("#FFFFFF"))
        painter = QPainter(pix)
        try:
            r = QRectF(2, 2, 68, 40)
            grad_info = style.get("grad")
            if grad_info:
                grad = QLinearGradient(r.topLeft(), r.bottomLeft())
                grad.setColorAt(0, QColor(grad_info[0]))
                grad.setColorAt(1, QColor(grad_info[1]))
                painter.setPen(QColor(style.get("stroke") or grad_info[1]))
                painter.setBrush(QBrush(grad))
            else:
                fill_col = QColor(style.get("fill") or "#000000")
                painter.setBrush(QBrush(fill_col))
                painter.setPen(QColor(style.get("stroke") or fill_col))

            font = QFont("Arial Black", 10, QFont.Weight.Bold)
            if style.get("warp") in ("slant_up", "slant_down"):
                font.setItalic(True)
            painter.setFont(font)

            if style.get("shadow"):
                painter.save()
                painter.setPen(QColor("#B0B0B0"))
                painter.drawText(r.translated(2, 2), Qt.AlignmentFlag.AlignCenter, "WordArt")
                painter.restore()

            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, "WordArt")
        finally:
            painter.end()
        return QIcon(pix)

    def _select_style(self, index: int) -> None:
        self.selected_style_index = index
        for i, btn in enumerate(self.style_buttons):
            btn.setChecked(i == index)

    def get_selected_style(self) -> dict[str, Any]:
        """Return the dictionary configuration of the chosen WordArt style."""
        return dict(WORDART_30_STYLES[self.selected_style_index])

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("艺术字库"))
        self.lbl_title.setText(safe_tr("选择艺术字样式:"))


class EditWordArtTextDialog(QDialog):
    """Dialog for editing WordArt text string, font, size, bold and italic."""

    def __init__(
        self,
        initial_text: str = "",
        initial_font: str = "Arial Black",
        initial_size: int = 36,
        bold: bool = True,
        italic: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.initial_text = initial_text or safe_tr("请在此键入您自己的内容")
        self.initial_font = initial_font
        self.initial_size = initial_size
        self.initial_bold = bold
        self.initial_italic = italic
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("编辑“艺术字”文字"))
        self.resize(460, 280)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # Row 1: Font, Size, Bold, Italic
        top_row = QHBoxLayout()
        self.lbl_font = QLabel(safe_tr("字体(&F):"), self)
        self.combo_font = QComboBox(self)
        for f in ["Arial Black", "Impact", "Arial", "Times New Roman", "Georgia", "Trebuchet MS", "Verdana"]:
            self.combo_font.addItem(f)
        idx_f = self.combo_font.findText(self.initial_font)
        if idx_f >= 0:
            self.combo_font.setCurrentIndex(idx_f)

        self.lbl_size = QLabel(safe_tr("字号(&S):"), self)
        self.combo_size = QComboBox(self)
        for sz in [20, 24, 28, 32, 36, 40, 44, 48, 54, 60, 66, 72, 80, 96]:
            self.combo_size.addItem(str(sz), sz)
        idx_sz = self.combo_size.findData(self.initial_size)
        if idx_sz >= 0:
            self.combo_size.setCurrentIndex(idx_sz)

        self.btn_bold = QPushButton("B", self)
        self.btn_bold.setCheckable(True)
        self.btn_bold.setChecked(self.initial_bold)
        self.btn_bold.setFixedWidth(28)
        font_b = self.btn_bold.font()
        font_b.setBold(True)
        self.btn_bold.setFont(font_b)

        self.btn_italic = QPushButton("I", self)
        self.btn_italic.setCheckable(True)
        self.btn_italic.setChecked(self.initial_italic)
        self.btn_italic.setFixedWidth(28)
        font_i = self.btn_italic.font()
        font_i.setItalic(True)
        self.btn_italic.setFont(font_i)

        top_row.addWidget(self.lbl_font)
        top_row.addWidget(self.combo_font, 1)
        top_row.addWidget(self.lbl_size)
        top_row.addWidget(self.combo_size)
        top_row.addWidget(self.btn_bold)
        top_row.addWidget(self.btn_italic)
        main_layout.addLayout(top_row)

        # Row 2: Text input area
        self.lbl_text = QLabel(safe_tr("文字(&T):"), self)
        main_layout.addWidget(self.lbl_text)

        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setPlainText(self.initial_text)
        main_layout.addWidget(self.text_edit, 1)

        # Connect live font update
        self.combo_font.currentTextChanged.connect(self._update_editor_font)
        self.combo_size.currentIndexChanged.connect(self._update_editor_font)
        self.btn_bold.toggled.connect(self._update_editor_font)
        self.btn_italic.toggled.connect(self._update_editor_font)
        self._update_editor_font()

        # OK / Cancel Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def _update_editor_font(self) -> None:
        font_name = self.combo_font.currentText()
        font_sz = self.combo_size.currentData() or 18
        # Scaled down font size for editor area readability
        f = QFont(font_name, min(24, max(12, int(font_sz // 2))))
        f.setBold(self.btn_bold.isChecked())
        f.setItalic(self.btn_italic.isChecked())
        self.text_edit.setFont(f)

    def get_wordart_data(self) -> dict[str, Any]:
        """Return the edited WordArt text and typography configuration."""
        return {
            "text": self.text_edit.toPlainText(),
            "font": self.combo_font.currentText(),
            "size": self.combo_size.currentData() or 36,
            "bold": self.btn_bold.isChecked(),
            "italic": self.btn_italic.isChecked(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("编辑“艺术字”文字"))
        self.lbl_font.setText(safe_tr("字体(&F):"))
        self.lbl_size.setText(safe_tr("字号(&S):"))
        self.lbl_text.setText(safe_tr("文字(&T):"))
