"""Patterns tab for FormatCellsDialog."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.dialogs.pattern_defs import (
    PATTERN_NAMES,
    PATTERNS,
    create_pattern_brush,
    create_pattern_pixmap,
)


def safe_tr(text: str) -> str:
    return QCoreApplication.translate("PatternsTab", text)


STANDARD_PALETTE = [
    "#000000",
    "#993300",
    "#333300",
    "#003300",
    "#003366",
    "#000080",
    "#333399",
    "#333333",
    "#800000",
    "#FF6600",
    "#808000",
    "#008000",
    "#008080",
    "#0000FF",
    "#666699",
    "#808080",
    "#FF0000",
    "#FF9900",
    "#99CC00",
    "#339966",
    "#33CCCC",
    "#3366FF",
    "#800080",
    "#999999",
    "#FF00FF",
    "#FFCC00",
    "#FFFF00",
    "#00FF00",
    "#00FFFF",
    "#00CCFF",
    "#993366",
    "#C0C0C0",
    "#FF99CC",
    "#FFCC99",
    "#FFFF99",
    "#CCFFCC",
    "#CCFFFF",
    "#99CCFF",
    "#CC99FF",
    "#FFFFFF",
]


class PatternChooserDialog(QDialog):
    """Popup dialog to select one of the 54 patterns and pattern color."""

    def __init__(
        self,
        current_pattern: str | None = None,
        pattern_color: str = "#000000",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("选择图案与颜色"))
        self.setModal(True)
        self.selected_pattern = current_pattern
        self.selected_color = pattern_color

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 1. 54 Patterns Grid
        layout.addWidget(QLabel(safe_tr("图案(&P):")))
        grid_patterns = QGridLayout()
        grid_patterns.setSpacing(4)

        row, col = 0, 0
        for pat_key in PATTERNS:
            btn = QPushButton()
            btn.setFixedSize(28, 24)
            btn.setIcon(QIcon(create_pattern_pixmap(pat_key, "#000000", "#FFFFFF", (20, 16))))
            btn.setIconSize(QSize(20, 16))
            btn.setToolTip(PATTERN_NAMES.get(pat_key, pat_key))
            btn.clicked.connect(lambda _, k=pat_key: self._on_pattern_clicked(k))
            grid_patterns.addWidget(btn, row, col)
            col += 1
            if col >= 9:
                col = 0
                row += 1
        layout.addLayout(grid_patterns)

        # 2. Pattern Color Palette
        layout.addWidget(QLabel(safe_tr("图案颜色(&C):")))
        grid_colors = QGridLayout()
        grid_colors.setSpacing(3)
        row, col = 0, 0
        for c in STANDARD_PALETTE:
            btn = QPushButton()
            btn.setFixedSize(18, 18)
            btn.setStyleSheet(f"background-color: {c}; border: 1px solid #999;")
            btn.clicked.connect(lambda _, clr=c: self._on_color_clicked(clr))
            grid_colors.addWidget(btn, row, col)
            col += 1
            if col >= 10:
                col = 0
                row += 1
        layout.addLayout(grid_colors)

        # Close button
        btn_close = QPushButton(safe_tr("完成"))
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _on_pattern_clicked(self, pat_key: str) -> None:
        self.selected_pattern = pat_key

    def _on_color_clicked(self, clr: str) -> None:
        self.selected_color = clr


class PatternSampleWidget(QWidget):
    """Preview box displaying background color and pattern brush."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(120, 60)
        self.bg_color: str | None = None
        self.pattern: str | None = None
        self.pattern_color: str | None = "#000000"

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        rect = self.rect().adjusted(1, 1, -1, -1)

        # Base background
        if self.bg_color:
            painter.fillRect(rect, QColor(self.bg_color))
        else:
            painter.fillRect(rect, Qt.GlobalColor.white)

        # Pattern overlay
        if self.pattern:
            fg = self.pattern_color or "#000000"
            bg = self.bg_color or "#FFFFFF"
            brush = create_pattern_brush(self.pattern, fg, bg)
            painter.fillRect(rect, brush)

        # Border
        painter.setPen(QColor("#A0A0A0"))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()


class PatternsTab(QWidget):
    """Tab 5: Cell shading background color and pattern fills."""

    def __init__(
        self,
        bg_color: str | None = None,
        pattern: str | None = None,
        pattern_color: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._bg_color = bg_color
        self._pattern = pattern
        self._pattern_color = pattern_color or "#000000"

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)

        # Left Column: Cell shading palette
        self.grp_shading = QGroupBox(safe_tr("单元格底纹"))
        shading_layout = QVBoxLayout(self.grp_shading)
        shading_layout.setSpacing(8)

        # No color button
        self.btn_no_color = QPushButton(safe_tr("无颜色(&N)"))
        self.btn_no_color.clicked.connect(self._on_no_color_clicked)
        shading_layout.addWidget(self.btn_no_color)

        # 40 Color Grid
        self.color_grid = QGridLayout()
        self.color_grid.setSpacing(4)
        row, col = 0, 0
        for c in STANDARD_PALETTE:
            btn = QPushButton()
            btn.setFixedSize(22, 20)
            btn.setStyleSheet(f"background-color: {c}; border: 1px solid #999;")
            btn.clicked.connect(lambda _, clr=c: self.set_bg_color(clr))
            self.color_grid.addWidget(btn, row, col)
            col += 1
            if col >= 8:
                col = 0
                row += 1
        shading_layout.addLayout(self.color_grid)

        # Pattern button
        pat_row = QHBoxLayout()
        self.lbl_pattern = QLabel(safe_tr("图案(&P):"))
        self.btn_pattern = QPushButton(safe_tr("图案样式…"))
        self.btn_pattern.clicked.connect(self._open_pattern_chooser)
        pat_row.addWidget(self.lbl_pattern)
        pat_row.addWidget(self.btn_pattern)
        shading_layout.addLayout(pat_row)

        main_layout.addWidget(self.grp_shading, 2)

        # Right Column: Sample box
        right_layout = QVBoxLayout()
        self.grp_sample = QGroupBox(safe_tr("示例"))
        s_layout = QVBoxLayout(self.grp_sample)
        self.sample_box = PatternSampleWidget()
        s_layout.addWidget(self.sample_box)
        right_layout.addWidget(self.grp_sample)
        right_layout.addStretch(1)

        main_layout.addLayout(right_layout, 1)

        self.update_sample()

    def _on_no_color_clicked(self) -> None:
        self._bg_color = None
        self.update_sample()

    def set_bg_color(self, color_hex: str | None) -> None:
        self._bg_color = color_hex
        self.update_sample()

    def set_pattern(self, pattern_name: str | None) -> None:
        self._pattern = pattern_name
        self.update_sample()

    def set_pattern_color(self, color_hex: str | None) -> None:
        self._pattern_color = color_hex or "#000000"
        self.update_sample()

    def _open_pattern_chooser(self) -> None:
        dlg = PatternChooserDialog(
            current_pattern=self._pattern,
            pattern_color=self._pattern_color,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._pattern = dlg.selected_pattern
            self._pattern_color = dlg.selected_color
            self.update_sample()

    def update_sample(self) -> None:
        self.sample_box.bg_color = self._bg_color
        self.sample_box.pattern = self._pattern
        self.sample_box.pattern_color = self._pattern_color
        self.sample_box.update()

    def get_patterns(self) -> dict[str, Any]:
        return {
            "bg_color": self._bg_color,
            "pattern": self._pattern,
            "pattern_color": self._pattern_color,
        }

    def retranslate_ui(self) -> None:
        self.grp_shading.setTitle(safe_tr("单元格底纹"))
        self.btn_no_color.setText(safe_tr("无颜色(&N)"))
        self.lbl_pattern.setText(safe_tr("图案(&P):"))
        self.btn_pattern.setText(safe_tr("图案样式…"))
        self.grp_sample.setTitle(safe_tr("示例"))
        self.update_sample()
