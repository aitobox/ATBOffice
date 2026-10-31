"""Classic Customize List (Bulleted / Numbered / Outline) Dialog for Quire.

Ported from Word 2003 / .vibeoffice/public/quire/js/dialogs.js:536 (G.customizeList).
Allows configuring list level numbering formats, fonts, starting offsets,
alignments, text indents, and following delimiters with live preview.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely for CustomizeListDialog."""
    return QCoreApplication.translate("CustomizeListDialog", text)


NUMBER_STYLES = [
    ("decimal", "1, 2, 3, ..."),
    ("upperRoman", "I, II, III, ..."),
    ("lowerRoman", "i, ii, iii, ..."),
    ("upperLetter", "A, B, C, ..."),
    ("lowerLetter", "a, b, c, ..."),
    ("ordinal", "1st, 2nd, 3rd, ..."),
    ("decimalZero", "01, 02, 03, ..."),
    ("bullet", safe_tr("项目符号")),
    ("none", safe_tr("(无)")),
]


class ListPreviewWidget(QFrame):
    """Mini preview canvas rendering simulated list items and indents."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedSize(160, 160)
        self.setStyleSheet("background-color: #FFFFFF; border: 1px solid #7F9DB9;")

        self._level_data: dict[str, Any] = {
            "fmt": "decimal",
            "text": "%1.",
            "start": 1,
            "aligned_at": 0.0,
            "indent_at": 21.0,
            "glyph": "•",
        }

    def update_level(self, data: dict[str, Any]) -> None:
        """Update preview parameters and repaint."""
        self._level_data = dict(data)
        self.update()

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = QFont("Arial", 8)
        painter.setFont(font)

        fmt = self._level_data.get("fmt", "decimal")
        raw_text = self._level_data.get("text", "%1.")
        start = self._level_data.get("start", 1)
        aligned_at = float(self._level_data.get("aligned_at", 0.0))
        indent_at = float(self._level_data.get("indent_at", 21.0))
        glyph = self._level_data.get("glyph", "•")

        # Scale factor for 160px canvas
        scale = 0.8

        for i in range(3):
            y = 25 + i * 40
            val = start + i

            if fmt == "bullet":
                prefix = glyph
            elif fmt == "none":
                prefix = ""
            elif fmt == "upperRoman":
                romans = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
                prefix = f"{romans[(val - 1) % len(romans)]}."
            elif fmt == "lowerRoman":
                romans = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]
                prefix = f"{romans[(val - 1) % len(romans)]}."
            elif fmt == "upperLetter":
                prefix = f"{chr(ord('A') + (val - 1) % 26)}."
            elif fmt == "lowerLetter":
                prefix = f"{chr(ord('a') + (val - 1) % 26)}."
            else:
                prefix = raw_text.replace("%1", str(val)) if "%1" in raw_text else f"{val}."

            num_x = 10 + int(aligned_at * scale)
            text_x = 10 + int(indent_at * scale)
            if text_x < num_x + 14:
                text_x = num_x + 14

            # Draw prefix
            painter.setPen(QColor("#000000"))
            painter.drawText(num_x, y, prefix)

            # Draw simulated text lines
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#888888"))
            painter.drawRect(text_x, y - 8, max(20, self.width() - text_x - 15), 4)
            painter.drawRect(text_x, y - 2, max(10, self.width() - text_x - 35), 4)

        painter.end()


class CustomizeListDialog(QDialog):
    """Word 2003 styled List Customization Wizard and Dialog."""

    def __init__(
        self,
        kind: str = "number",  # "bullet", "number", "outline"
        initial_level: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self.current_level = initial_level
        self._levels: list[dict[str, Any]] = []

        # Initialize default 9 levels
        for lvl in range(9):
            if kind == "bullet":
                glyph = ["•", "○", "■", "◆", "➢", "★", "▪", "▫", "—"][lvl % 9]
                self._levels.append(
                    {
                        "fmt": "bullet",
                        "text": glyph,
                        "glyph": glyph,
                        "start": 1,
                        "jc": "left",
                        "aligned_at": 0.0,
                        "indent_at": 21.0 * (lvl + 1),
                        "tab_after": 21.0 * (lvl + 1),
                        "suff": "tab",
                    }
                )
            elif kind == "outline":
                self._levels.append(
                    {
                        "fmt": "decimal",
                        "text": f"%{lvl + 1}.",
                        "glyph": "•",
                        "start": 1,
                        "jc": "left",
                        "aligned_at": 0.0,
                        "indent_at": 21.0 * (lvl + 1),
                        "tab_after": 21.0 * (lvl + 1),
                        "suff": "tab",
                    }
                )
            else:
                self._levels.append(
                    {
                        "fmt": "decimal",
                        "text": "%1.",
                        "glyph": "•",
                        "start": 1,
                        "jc": "left",
                        "aligned_at": 0.0,
                        "indent_at": 21.0,
                        "tab_after": 21.0,
                        "suff": "tab",
                    }
                )

        self.setMinimumWidth(520)
        self._setup_ui()
        self._load_level(self.current_level)
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        body_layout = QHBoxLayout()

        # 1. Level selector for outline
        if self.kind == "outline":
            col_level = QVBoxLayout()
            self.lbl_level = QLabel(self)
            col_level.addWidget(self.lbl_level)
            self.list_levels = QListWidget(self)
            self.list_levels.setFixedWidth(60)
            for i in range(1, 10):
                self.list_levels.addItem(str(i))
            self.list_levels.currentRowChanged.connect(self._on_level_changed)
            col_level.addWidget(self.list_levels)
            body_layout.addLayout(col_level)

        # 2. Main properties column
        col_props = QVBoxLayout()

        # Format & Style Group
        self.grp_format = QGroupBox(self)
        grid_fmt = QGridLayout(self.grp_format)

        self.lbl_num_fmt = QLabel(self.grp_format)
        self.edit_num_fmt = QLineEdit(self.grp_format)
        self.edit_num_fmt.textChanged.connect(self._trigger_preview)
        grid_fmt.addWidget(self.lbl_num_fmt, 0, 0)
        grid_fmt.addWidget(self.edit_num_fmt, 0, 1)

        self.lbl_num_style = QLabel(self.grp_format)
        self.combo_num_style = QComboBox(self.grp_format)
        for val, label in NUMBER_STYLES:
            self.combo_num_style.addItem(label, val)
        self.combo_num_style.currentIndexChanged.connect(self._on_style_changed)
        grid_fmt.addWidget(self.lbl_num_style, 1, 0)
        grid_fmt.addWidget(self.combo_num_style, 1, 1)

        self.lbl_start = QLabel(self.grp_format)
        self.spin_start = QSpinBox(self.grp_format)
        self.spin_start.setRange(0, 9999)
        self.spin_start.setValue(1)
        self.spin_start.valueChanged.connect(self._trigger_preview)
        grid_fmt.addWidget(self.lbl_start, 2, 0)
        grid_fmt.addWidget(self.spin_start, 2, 1)

        col_props.addWidget(self.grp_format)

        # Position Group
        self.grp_position = QGroupBox(self)
        grid_pos = QGridLayout(self.grp_position)

        self.lbl_align = QLabel(self.grp_position)
        self.combo_align = QComboBox(self.grp_position)
        self.combo_align.addItem(safe_tr("左对齐"), "left")
        self.combo_align.addItem(safe_tr("居中"), "center")
        self.combo_align.addItem(safe_tr("右对齐"), "right")
        self.combo_align.currentIndexChanged.connect(self._trigger_preview)
        grid_pos.addWidget(self.lbl_align, 0, 0)
        grid_pos.addWidget(self.combo_align, 0, 1)

        self.lbl_aligned_at = QLabel(self.grp_position)
        self.spin_aligned_at = QDoubleSpinBox(self.grp_position)
        self.spin_aligned_at.setRange(0.0, 1584.0)
        self.spin_aligned_at.setSingleStep(1.0)
        self.spin_aligned_at.setSuffix(" pt")
        self.spin_aligned_at.valueChanged.connect(self._trigger_preview)
        grid_pos.addWidget(self.lbl_aligned_at, 1, 0)
        grid_pos.addWidget(self.spin_aligned_at, 1, 1)

        col_props.addWidget(self.grp_position)

        # Text Indent Group
        self.grp_text_pos = QGroupBox(self)
        grid_text = QGridLayout(self.grp_text_pos)

        self.lbl_indent_at = QLabel(self.grp_text_pos)
        self.spin_indent_at = QDoubleSpinBox(self.grp_text_pos)
        self.spin_indent_at.setRange(0.0, 1584.0)
        self.spin_indent_at.setSingleStep(1.0)
        self.spin_indent_at.setSuffix(" pt")
        self.spin_indent_at.valueChanged.connect(self._trigger_preview)
        grid_text.addWidget(self.lbl_indent_at, 0, 0)
        grid_text.addWidget(self.spin_indent_at, 0, 1)

        self.lbl_tab_after = QLabel(self.grp_text_pos)
        self.spin_tab_after = QDoubleSpinBox(self.grp_text_pos)
        self.spin_tab_after.setRange(0.0, 1584.0)
        self.spin_tab_after.setSingleStep(1.0)
        self.spin_tab_after.setSuffix(" pt")
        self.spin_tab_after.valueChanged.connect(self._trigger_preview)
        grid_text.addWidget(self.lbl_tab_after, 1, 0)
        grid_text.addWidget(self.spin_tab_after, 1, 1)

        self.lbl_follow = QLabel(self.grp_text_pos)
        self.combo_follow = QComboBox(self.grp_text_pos)
        self.combo_follow.addItem(safe_tr("制表符"), "tab")
        self.combo_follow.addItem(safe_tr("空格"), "space")
        self.combo_follow.addItem(safe_tr("无特别标示"), "nothing")
        grid_text.addWidget(self.lbl_follow, 2, 0)
        grid_text.addWidget(self.combo_follow, 2, 1)

        col_props.addWidget(self.grp_text_pos)
        body_layout.addLayout(col_props, stretch=1)

        # 3. Preview Column
        col_preview = QVBoxLayout()
        self.lbl_preview_title = QLabel(self)
        col_preview.addWidget(self.lbl_preview_title)
        self.preview_widget = ListPreviewWidget(self)
        col_preview.addWidget(self.preview_widget)
        col_preview.addStretch(1)
        body_layout.addLayout(col_preview)

        main_layout.addLayout(body_layout)

        # Bottom Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def _on_level_changed(self, row: int) -> None:
        if 0 <= row < len(self._levels):
            self._save_level(self.current_level)
            self.current_level = row
            self._load_level(self.current_level)

    def _on_style_changed(self) -> None:
        val = self.combo_num_style.currentData()
        self.spin_start.setEnabled(val != "bullet" and val != "none")
        if val == "bullet":
            if not self.edit_num_fmt.text() or self.edit_num_fmt.text().startswith("%"):
                self.edit_num_fmt.setText("•")
        elif val != "none" and not self.edit_num_fmt.text():
            self.edit_num_fmt.setText("%1.")
        self._trigger_preview()

    def _load_level(self, lvl: int) -> None:
        data = self._levels[lvl]
        fmt = data.get("fmt", "decimal")
        idx = self.combo_num_style.findData(fmt)
        if idx >= 0:
            self.combo_num_style.setCurrentIndex(idx)

        self.edit_num_fmt.setText(str(data.get("text", "%1.")))
        self.spin_start.setValue(int(data.get("start", 1)))

        jc = data.get("jc", "left")
        idx = self.combo_align.findData(jc)
        if idx >= 0:
            self.combo_align.setCurrentIndex(idx)

        self.spin_aligned_at.setValue(float(data.get("aligned_at", 0.0)))
        self.spin_indent_at.setValue(float(data.get("indent_at", 21.0)))
        self.spin_tab_after.setValue(float(data.get("tab_after", 21.0)))

        suff = data.get("suff", "tab")
        idx = self.combo_follow.findData(suff)
        if idx >= 0:
            self.combo_follow.setCurrentIndex(idx)

        self._trigger_preview()

    def _save_level(self, lvl: int) -> None:
        data = self._levels[lvl]
        data["fmt"] = self.combo_num_style.currentData() or "decimal"
        data["text"] = self.edit_num_fmt.text()
        data["start"] = self.spin_start.value()
        data["jc"] = self.combo_align.currentData() or "left"
        data["aligned_at"] = self.spin_aligned_at.value()
        data["indent_at"] = self.spin_indent_at.value()
        data["tab_after"] = self.spin_tab_after.value()
        data["suff"] = self.combo_follow.currentData() or "tab"
        if data["fmt"] == "bullet":
            data["glyph"] = self.edit_num_fmt.text() or "•"

    def _trigger_preview(self) -> None:
        self._save_level(self.current_level)
        self.preview_widget.update_level(self._levels[self.current_level])

    def get_customized_level(self) -> dict[str, Any]:
        """Return the dictionary of configured properties for current level."""
        self._save_level(self.current_level)
        return dict(self._levels[self.current_level])

    def get_all_levels(self) -> list[dict[str, Any]]:
        """Return all configured levels."""
        self._save_level(self.current_level)
        return [dict(lv) for lv in self._levels]

    def retranslate_ui(self) -> None:
        """Localize UI strings."""
        if self.kind == "bullet":
            self.setWindowTitle(safe_tr("自定义项目符号列表"))
        elif self.kind == "outline":
            self.setWindowTitle(safe_tr("自定义多级符号列表"))
        else:
            self.setWindowTitle(safe_tr("自定义编号列表"))

        if hasattr(self, "lbl_level"):
            self.lbl_level.setText(safe_tr("级别(&V):"))

        self.grp_format.setTitle(safe_tr("编号格式"))
        self.lbl_num_fmt.setText(safe_tr("编号格式(&O):"))
        self.lbl_num_style.setText(safe_tr("编号样式(&N):"))
        self.lbl_start.setText(safe_tr("起始编号(&S):"))

        self.grp_position.setTitle(safe_tr("编号位置"))
        self.lbl_align.setText(safe_tr("对齐方式(&A):"))
        self.lbl_aligned_at.setText(safe_tr("对齐位置(&L):"))

        self.grp_text_pos.setTitle(safe_tr("文字位置"))
        self.lbl_indent_at.setText(safe_tr("缩进位置(&T):"))
        self.lbl_tab_after.setText(safe_tr("制表位位置(&P):"))
        self.lbl_follow.setText(safe_tr("编号之后(&F):"))

        self.lbl_preview_title.setText(safe_tr("预览(&R)"))
