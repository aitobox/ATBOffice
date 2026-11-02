"""Page Formatting Dialogs for Quire Writer.

Includes:
- DropCapDialog: Drop cap formatting (首字下沉)
- TextDirectionDialog: Text direction in cells/text boxes (文字方向)
- WatermarkDialog: Printed watermark settings (水印设置)
- PageNumbersDialog: Insert page numbers & format (插入页码)
- ChangeCaseDialog: Change text capitalization case (更改大小写)
- DocumentThemeDialog: Document theme selector (文档主题选择)
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("PageFormattingDialogs", text)


class DropCapDialog(QDialog):
    """Drop Cap formatting dialog (首字下沉)."""

    def __init__(
        self,
        initial_position: str = "dropped",
        initial_font: str = "宋体",
        initial_lines: int = 3,
        initial_distance: float = 0.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("首字下沉"))
        self.resize(320, 240)

        layout = QVBoxLayout(self)

        # Position group
        self.grp_position = QGroupBox(safe_tr("位置"), self)
        l_pos = QHBoxLayout(self.grp_position)
        self.radio_none = QRadioButton(safe_tr("无(&N)"), self.grp_position)
        self.radio_dropped = QRadioButton(safe_tr("下沉(&D)"), self.grp_position)
        self.radio_margin = QRadioButton(safe_tr("悬挂(&M)"), self.grp_position)

        if initial_position == "none":
            self.radio_none.setChecked(True)
        elif initial_position == "margin":
            self.radio_margin.setChecked(True)
        else:
            self.radio_dropped.setChecked(True)

        l_pos.addWidget(self.radio_none)
        l_pos.addWidget(self.radio_dropped)
        l_pos.addWidget(self.radio_margin)
        layout.addWidget(self.grp_position)

        # Options group
        self.grp_options = QGroupBox(safe_tr("选项"), self)
        f_layout = QFormLayout(self.grp_options)

        self.combo_font = QComboBox(self.grp_options)
        self.combo_font.addItems([
            "宋体",
            "黑体",
            "仿宋",
            "楷体",
            "微软雅黑",
            "Arial",
            "Times New Roman",
            "Courier New",
            "Georgia",
            "Verdana",
        ])
        idx = self.combo_font.findText(initial_font)
        if idx >= 0:
            self.combo_font.setCurrentIndex(idx)

        self.spin_lines = QSpinBox(self.grp_options)
        self.spin_lines.setRange(1, 10)
        self.spin_lines.setValue(initial_lines)

        self.spin_distance = QDoubleSpinBox(self.grp_options)
        self.spin_distance.setRange(0.0, 50.0)
        self.spin_distance.setSingleStep(0.1)
        self.spin_distance.setValue(initial_distance)
        self.spin_distance.setSuffix(safe_tr(" 厘米"))

        self.lbl_font = QLabel(safe_tr("字体(&F):"), self)
        self.lbl_lines = QLabel(safe_tr("下沉行数(&L):"), self)
        self.lbl_dist = QLabel(safe_tr("距正文(&T):"), self)

        f_layout.addRow(self.lbl_font, self.combo_font)
        f_layout.addRow(self.lbl_lines, self.spin_lines)
        f_layout.addRow(self.lbl_dist, self.spin_distance)
        layout.addWidget(self.grp_options)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_drop_cap_data(self) -> dict[str, Any]:
        pos = "dropped"
        if self.radio_none.isChecked():
            pos = "none"
        elif self.radio_margin.isChecked():
            pos = "margin"

        return {
            "position": pos,
            "font": self.combo_font.currentText(),
            "lines": self.spin_lines.value(),
            "distance_cm": self.spin_distance.value(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("首字下沉"))
        self.grp_position.setTitle(safe_tr("位置"))
        self.radio_none.setText(safe_tr("无(&N)"))
        self.radio_dropped.setText(safe_tr("下沉(&D)"))
        self.radio_margin.setText(safe_tr("悬挂(&M)"))
        self.grp_options.setTitle(safe_tr("选项"))
        self.lbl_font.setText(safe_tr("字体(&F):"))
        self.lbl_lines.setText(safe_tr("下沉行数(&L):"))
        self.lbl_dist.setText(safe_tr("距正文(&T):"))
        self.spin_distance.setSuffix(safe_tr(" 厘米"))


class TextDirectionDialog(QDialog):
    """Text Direction Dialog for text boxes and table cells (文字方向)."""

    def __init__(self, initial_direction: str = "horz", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("文字方向"))
        self.resize(280, 200)

        layout = QVBoxLayout(self)
        self.lbl_hint = QLabel(safe_tr("方向应用于所选文本框或表格单元格。"), self)
        self.lbl_hint.setWordWrap(True)
        layout.addWidget(self.lbl_hint)

        self.grp_direction = QGroupBox(safe_tr("方向"), self)
        l_dir = QVBoxLayout(self.grp_direction)

        self.radio_horz = QRadioButton(safe_tr("水平(&H)"), self.grp_direction)
        self.radio_vert = QRadioButton(safe_tr("垂直（从上到下）(&V)"), self.grp_direction)
        self.radio_vert270 = QRadioButton(safe_tr("垂直（从下到上）(&B)"), self.grp_direction)

        if initial_direction == "vert":
            self.radio_vert.setChecked(True)
        elif initial_direction == "vert270":
            self.radio_vert270.setChecked(True)
        else:
            self.radio_horz.setChecked(True)

        l_dir.addWidget(self.radio_horz)
        l_dir.addWidget(self.radio_vert)
        l_dir.addWidget(self.radio_vert270)
        layout.addWidget(self.grp_direction)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_direction(self) -> str:
        if self.radio_vert.isChecked():
            return "vert"
        if self.radio_vert270.isChecked():
            return "vert270"
        return "horz"

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("文字方向"))
        self.lbl_hint.setText(safe_tr("方向应用于所选文本框或表格单元格。"))
        self.grp_direction.setTitle(safe_tr("方向"))
        self.radio_horz.setText(safe_tr("水平(&H)"))
        self.radio_vert.setText(safe_tr("垂直（从上到下）(&V)"))
        self.radio_vert270.setText(safe_tr("垂直（从下到上）(&B)"))


class WatermarkDialog(QDialog):
    """Printed Watermark dialog (水印设置)."""

    def __init__(
        self,
        watermark_type: str = "none",
        picture_path: str = "",
        text_content: str = "绝密",
        font_name: str = "宋体",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("水印"))
        self.resize(380, 420)

        layout = QVBoxLayout(self)

        self.button_group = QButtonGroup(self)
        self.radio_none = QRadioButton(safe_tr("无水印(&N)"), self)
        self.radio_picture = QRadioButton(safe_tr("图片水印(&P)"), self)
        self.radio_text = QRadioButton(safe_tr("文字水印(&W)"), self)

        self.button_group.addButton(self.radio_none, 0)
        self.button_group.addButton(self.radio_picture, 1)
        self.button_group.addButton(self.radio_text, 2)

        layout.addWidget(self.radio_none)

        # Picture group
        layout.addWidget(self.radio_picture)
        self.grp_picture = QGroupBox(self)
        p_layout = QFormLayout(self.grp_picture)

        h_pic = QHBoxLayout()
        self.edit_pic_path = QLineEdit(picture_path, self.grp_picture)
        self.btn_browse = QPushButton(safe_tr("选择图片..."), self.grp_picture)
        self.btn_browse.clicked.connect(self._browse_picture)
        h_pic.addWidget(self.edit_pic_path)
        h_pic.addWidget(self.btn_browse)

        self.combo_scale = QComboBox(self.grp_picture)
        self.combo_scale.addItems(["Auto", "500%", "200%", "150%", "100%", "50%"])
        self.check_washout = QCheckBox(safe_tr("冲蚀(&W)"), self.grp_picture)
        self.check_washout.setChecked(True)

        self.lbl_pic_select = QLabel(safe_tr("图片:"), self)
        self.lbl_scale = QLabel(safe_tr("缩放:"), self)
        p_layout.addRow(self.lbl_pic_select, h_pic)
        p_layout.addRow(self.lbl_scale, self.combo_scale)
        p_layout.addRow("", self.check_washout)
        layout.addWidget(self.grp_picture)

        # Text group
        layout.addWidget(self.radio_text)
        self.grp_text = QGroupBox(self)
        t_layout = QFormLayout(self.grp_text)

        self.combo_text = QComboBox(self.grp_text)
        self.combo_text.setEditable(True)
        self.combo_text.addItems([
            "绝密",
            "机密",
            "内部参考",
            "样本",
            "草稿",
            "CONFIDENTIAL",
            "DO NOT COPY",
            "DRAFT",
            "ORIGINAL",
            "TOP SECRET",
        ])
        if text_content:
            self.combo_text.setEditText(text_content)

        self.combo_font = QComboBox(self.grp_text)
        self.combo_font.addItems([
            "宋体",
            "黑体",
            "楷体",
            "微软雅黑",
            "Arial",
            "Times New Roman",
            "Calibri",
        ])
        idx = self.combo_font.findText(font_name)
        if idx >= 0:
            self.combo_font.setCurrentIndex(idx)

        self.combo_size = QComboBox(self.grp_text)
        self.combo_size.addItems(
            ["Auto", "36", "40", "44", "48", "54", "60", "66", "72", "80", "96"]
        )

        self.color_selected = QColor("gray")
        self.btn_color = QPushButton(safe_tr("选择颜色..."), self.grp_text)
        self.btn_color.clicked.connect(self._choose_color)

        # Layout: diagonal or horizontal
        h_layout_radios = QHBoxLayout()
        self.radio_diagonal = QRadioButton(safe_tr("斜体/倾斜(&D)"), self.grp_text)
        self.radio_horizontal = QRadioButton(safe_tr("水平(&H)"), self.grp_text)
        self.radio_diagonal.setChecked(True)
        h_layout_radios.addWidget(self.radio_diagonal)
        h_layout_radios.addWidget(self.radio_horizontal)

        self.check_semitransparent = QCheckBox(safe_tr("半透明(&S)"), self.grp_text)
        self.check_semitransparent.setChecked(True)

        self.lbl_text = QLabel(safe_tr("文字(&T):"), self)
        self.lbl_t_font = QLabel(safe_tr("字体(&F):"), self)
        self.lbl_t_size = QLabel(safe_tr("字号(&Z):"), self)
        self.lbl_t_color = QLabel(safe_tr("颜色(&C):"), self)
        self.lbl_t_layout = QLabel(safe_tr("版式:"), self)

        t_layout.addRow(self.lbl_text, self.combo_text)
        t_layout.addRow(self.lbl_t_font, self.combo_font)
        t_layout.addRow(self.lbl_t_size, self.combo_size)
        t_layout.addRow(self.lbl_t_color, self.btn_color)
        t_layout.addRow(self.lbl_t_layout, h_layout_radios)
        t_layout.addRow("", self.check_semitransparent)
        layout.addWidget(self.grp_text)

        # State sync
        self.button_group.idToggled.connect(self._sync_enabled_states)
        if watermark_type == "picture":
            self.radio_picture.setChecked(True)
        elif watermark_type == "text":
            self.radio_text.setChecked(True)
        else:
            self.radio_none.setChecked(True)
        self._sync_enabled_states()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _sync_enabled_states(self) -> None:
        self.grp_picture.setEnabled(self.radio_picture.isChecked())
        self.grp_text.setEnabled(self.radio_text.isChecked())

    def _browse_picture(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            safe_tr("选择水印图片"),
            "",
            safe_tr("图片文件 (*.png *.jpg *.jpeg *.bmp *.svg)"),
        )
        if file_path:
            self.edit_pic_path.setText(file_path)

    def _choose_color(self) -> None:
        col = QColorDialog.getColor(self.color_selected, self, safe_tr("选择水印文字颜色"))
        if col.isValid():
            self.color_selected = col

    def get_watermark_data(self) -> dict[str, Any]:
        wm_type = "none"
        if self.radio_picture.isChecked():
            wm_type = "picture"
        elif self.radio_text.isChecked():
            wm_type = "text"

        return {
            "type": wm_type,
            "picture_path": self.edit_pic_path.text(),
            "scale": self.combo_scale.currentText(),
            "washout": self.check_washout.isChecked(),
            "text": self.combo_text.currentText(),
            "font": self.combo_font.currentText(),
            "size": self.combo_size.currentText(),
            "color": self.color_selected.name(),
            "layout": "diagonal" if self.radio_diagonal.isChecked() else "horizontal",
            "semitransparent": self.check_semitransparent.isChecked(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("水印"))
        self.radio_none.setText(safe_tr("无水印(&N)"))
        self.radio_picture.setText(safe_tr("图片水印(&P)"))
        self.radio_text.setText(safe_tr("文字水印(&W)"))
        self.lbl_pic_select.setText(safe_tr("图片:"))
        self.btn_browse.setText(safe_tr("选择图片..."))
        self.lbl_scale.setText(safe_tr("缩放:"))
        self.check_washout.setText(safe_tr("冲蚀(&W)"))
        self.lbl_text.setText(safe_tr("文字(&T):"))
        self.lbl_t_font.setText(safe_tr("字体(&F):"))
        self.lbl_t_size.setText(safe_tr("字号(&Z):"))
        self.lbl_t_color.setText(safe_tr("颜色(&C):"))
        self.btn_color.setText(safe_tr("选择颜色..."))
        self.lbl_t_layout.setText(safe_tr("版式:"))
        self.radio_diagonal.setText(safe_tr("斜体/倾斜(&D)"))
        self.radio_horizontal.setText(safe_tr("水平(&H)"))
        self.check_semitransparent.setText(safe_tr("半透明(&S)"))


class PageNumbersDialog(QDialog):
    """Insert Page Numbers dialog (插入页码)."""

    def __init__(
        self,
        position: str = "footer",
        alignment: str = "right",
        show_first_page: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("页码"))
        self.resize(320, 200)

        layout = QVBoxLayout(self)
        f_layout = QFormLayout()

        self.combo_position = QComboBox(self)
        self.combo_position.addItem(safe_tr("页面底端（页脚）"), "footer")
        self.combo_position.addItem(safe_tr("页面顶端（页眉）"), "header")
        idx_pos = self.combo_position.findData(position)
        if idx_pos >= 0:
            self.combo_position.setCurrentIndex(idx_pos)

        self.combo_alignment = QComboBox(self)
        self.combo_alignment.addItem(safe_tr("左侧"), "left")
        self.combo_alignment.addItem(safe_tr("居中"), "center")
        self.combo_alignment.addItem(safe_tr("右侧"), "right")
        self.combo_alignment.addItem(safe_tr("内侧"), "inside")
        self.combo_alignment.addItem(safe_tr("外侧"), "outside")
        idx_align = self.combo_alignment.findData(alignment)
        if idx_align >= 0:
            self.combo_alignment.setCurrentIndex(idx_align)

        self.check_first_page = QCheckBox(safe_tr("首页显示页码(&S)"), self)
        self.check_first_page.setChecked(show_first_page)

        self.lbl_pos = QLabel(safe_tr("位置(&P):"), self)
        self.lbl_align = QLabel(safe_tr("对齐方式(&A):"), self)

        f_layout.addRow(self.lbl_pos, self.combo_position)
        f_layout.addRow(self.lbl_align, self.combo_alignment)
        f_layout.addRow("", self.check_first_page)
        layout.addLayout(f_layout)

        # Format options
        self.grp_format = QGroupBox(safe_tr("数字格式"), self)
        fmt_layout = QFormLayout(self.grp_format)
        self.combo_number_format = QComboBox(self.grp_format)
        self.combo_number_format.addItems([
            "1, 2, 3, ...",
            "a, b, c, ...",
            "A, B, C, ...",
            "i, ii, iii, ...",
            "I, II, III, ...",
        ])

        self.radio_continue = QRadioButton(safe_tr("续前节(&C)"), self.grp_format)
        self.radio_start_at = QRadioButton(safe_tr("起始页码(&A):"), self.grp_format)
        self.spin_start_at = QSpinBox(self.grp_format)
        self.spin_start_at.setRange(1, 99999)
        self.spin_start_at.setValue(1)
        self.radio_continue.setChecked(True)

        h_start = QHBoxLayout()
        h_start.addWidget(self.radio_start_at)
        h_start.addWidget(self.spin_start_at)

        self.lbl_num_fmt = QLabel(safe_tr("数字格式(&F):"), self.grp_format)
        fmt_layout.addRow(self.lbl_num_fmt, self.combo_number_format)
        fmt_layout.addRow(self.radio_continue)
        fmt_layout.addRow(h_start)
        layout.addWidget(self.grp_format)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_page_number_settings(self) -> dict[str, Any]:
        return {
            "position": self.combo_position.currentData(),
            "alignment": self.combo_alignment.currentData(),
            "show_first_page": self.check_first_page.isChecked(),
            "number_format": self.combo_number_format.currentText(),
            "continue_numbering": self.radio_continue.isChecked(),
            "start_at": self.spin_start_at.value() if self.radio_start_at.isChecked() else None,
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("页码"))
        self.lbl_pos.setText(safe_tr("位置(&P):"))
        self.lbl_align.setText(safe_tr("对齐方式(&A):"))
        self.check_first_page.setText(safe_tr("首页显示页码(&S)"))
        self.grp_format.setTitle(safe_tr("数字格式"))
        self.lbl_num_fmt.setText(safe_tr("数字格式(&F):"))
        self.radio_continue.setText(safe_tr("续前节(&C)"))
        self.radio_start_at.setText(safe_tr("起始页码(&A):"))


class ChangeCaseDialog(QDialog):
    """Change Text Case dialog (更改大小写)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("更改大小写"))
        self.resize(240, 180)

        layout = QVBoxLayout(self)

        self.radio_sentence = QRadioButton(safe_tr("句首字母大写(&S)"), self)
        self.radio_lower = QRadioButton(safe_tr("全部小写(&L)"), self)
        self.radio_upper = QRadioButton(safe_tr("全部大写(&U)"), self)
        self.radio_title = QRadioButton(safe_tr("词首字母大写(&T)"), self)
        self.radio_toggle = QRadioButton(safe_tr("切换大小写(&G)"), self)

        self.radio_sentence.setChecked(True)

        layout.addWidget(self.radio_sentence)
        layout.addWidget(self.radio_lower)
        layout.addWidget(self.radio_upper)
        layout.addWidget(self.radio_title)
        layout.addWidget(self.radio_toggle)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_case_mode(self) -> str:
        if self.radio_lower.isChecked():
            return "lower"
        if self.radio_upper.isChecked():
            return "upper"
        if self.radio_title.isChecked():
            return "title"
        if self.radio_toggle.isChecked():
            return "toggle"
        return "sentence"

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("更改大小写"))
        self.radio_sentence.setText(safe_tr("句首字母大写(&S)"))
        self.radio_lower.setText(safe_tr("全部小写(&L)"))
        self.radio_upper.setText(safe_tr("全部大写(&U)"))
        self.radio_title.setText(safe_tr("词首字母大写(&T)"))
        self.radio_toggle.setText(safe_tr("切换大小写(&G)"))


class DocumentThemeDialog(QDialog):
    """Document Theme Selector dialog (文档主题选择)."""

    THEMES = [
        "Office",
        "Apex",
        "Aspect",
        "Civic",
        "Concourse",
        "Equity",
        "Flow",
        "Foundry",
        "Median",
        "Metro",
        "Module",
        "Opulent",
        "Oriel",
        "Origin",
        "Paper",
        "Solstice",
        "Technic",
        "Trek",
        "Urban",
        "Verve",
    ]

    def __init__(self, current_theme: str = "Office", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("主题"))
        self.resize(300, 360)

        layout = QVBoxLayout(self)
        self.lbl_choose = QLabel(safe_tr("选择文档主题(&T):"), self)
        layout.addWidget(self.lbl_choose)

        self.list_themes = QListWidget(self)
        for t in self.THEMES:
            item = QListWidgetItem(t)
            self.list_themes.addItem(item)
            if t.lower() == current_theme.lower():
                self.list_themes.setCurrentItem(item)

        if not self.list_themes.currentItem() and self.list_themes.count() > 0:
            self.list_themes.setCurrentRow(0)

        layout.addWidget(self.list_themes)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_selected_theme(self) -> str:
        item = self.list_themes.currentItem()
        return item.text() if item else "Office"

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("主题"))
        self.lbl_choose.setText(safe_tr("选择文档主题(&T):"))
