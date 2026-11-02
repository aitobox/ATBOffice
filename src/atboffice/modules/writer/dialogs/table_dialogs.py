"""Table Operations Dialogs for Quire Writer.

Includes:
- InsertCellsDialog: Insert Cells (插入单元格)
- DeleteCellsDialog: Delete Cells (删除单元格)
- SplitCellsDialog: Split Table Cells (拆分单元格)
- TableAutoFormatDialog: Table AutoFormat Styles (表格自动套用格式)
- TableSortDialog: Sort Table or Text (表格/文字排序)
- TableFormulaDialog: Table Formula Calculation (表格公式)
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("TableDialogs", text)


class InsertCellsDialog(QDialog):
    """Insert Cells Options dialog (插入单元格)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("插入单元格"))
        self.resize(260, 180)

        layout = QVBoxLayout(self)

        self.radio_right = QRadioButton(safe_tr("活动单元格右移(&I)"), self)
        self.radio_down = QRadioButton(safe_tr("活动单元格下移(&D)"), self)
        self.radio_row = QRadioButton(safe_tr("整行插入(&R)"), self)
        self.radio_col = QRadioButton(safe_tr("整列插入(&C)"), self)

        self.radio_down.setChecked(True)

        layout.addWidget(self.radio_right)
        layout.addWidget(self.radio_down)
        layout.addWidget(self.radio_row)
        layout.addWidget(self.radio_col)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_action(self) -> str:
        if self.radio_right.isChecked():
            return "right"
        if self.radio_row.isChecked():
            return "row"
        if self.radio_col.isChecked():
            return "col"
        return "down"

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("插入单元格"))
        self.radio_right.setText(safe_tr("活动单元格右移(&I)"))
        self.radio_down.setText(safe_tr("活动单元格下移(&D)"))
        self.radio_row.setText(safe_tr("整行插入(&R)"))
        self.radio_col.setText(safe_tr("整列插入(&C)"))


class DeleteCellsDialog(QDialog):
    """Delete Cells Options dialog (删除单元格)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("删除单元格"))
        self.resize(260, 180)

        layout = QVBoxLayout(self)

        self.radio_left = QRadioButton(safe_tr("右侧单元格左移(&L)"), self)
        self.radio_up = QRadioButton(safe_tr("下方单元格上移(&U)"), self)
        self.radio_row = QRadioButton(safe_tr("删除整行(&R)"), self)
        self.radio_col = QRadioButton(safe_tr("删除整列(&C)"), self)

        self.radio_left.setChecked(True)

        layout.addWidget(self.radio_left)
        layout.addWidget(self.radio_up)
        layout.addWidget(self.radio_row)
        layout.addWidget(self.radio_col)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_action(self) -> str:
        if self.radio_up.isChecked():
            return "up"
        if self.radio_row.isChecked():
            return "row"
        if self.radio_col.isChecked():
            return "col"
        return "left"

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("删除单元格"))
        self.radio_left.setText(safe_tr("右侧单元格左移(&L)"))
        self.radio_up.setText(safe_tr("下方单元格上移(&U)"))
        self.radio_row.setText(safe_tr("删除整行(&R)"))
        self.radio_col.setText(safe_tr("删除整列(&C)"))


class SplitCellsDialog(QDialog):
    """Split Table Cells dialog (拆分单元格)."""

    def __init__(
        self,
        default_cols: int = 2,
        default_rows: int = 1,
        can_merge: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("拆分单元格"))
        self.resize(260, 160)

        layout = QVBoxLayout(self)
        f_layout = QFormLayout()

        self.spin_cols = QSpinBox(self)
        self.spin_cols.setRange(1, 63)
        self.spin_cols.setValue(default_cols)

        self.spin_rows = QSpinBox(self)
        self.spin_rows.setRange(1, 100)
        self.spin_rows.setValue(default_rows)

        self.chk_merge_before_split = QCheckBox(safe_tr("拆分前合并单元格(&M)"), self)
        self.chk_merge_before_split.setChecked(can_merge)

        self.lbl_cols = QLabel(safe_tr("列数(&C):"), self)
        self.lbl_rows = QLabel(safe_tr("行数(&R):"), self)

        f_layout.addRow(self.lbl_cols, self.spin_cols)
        f_layout.addRow(self.lbl_rows, self.spin_rows)
        f_layout.addRow("", self.chk_merge_before_split)
        layout.addLayout(f_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_dimensions(self) -> tuple[int, int, bool]:
        return (
            self.spin_cols.value(),
            self.spin_rows.value(),
            self.chk_merge_before_split.isChecked(),
        )

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("拆分单元格"))
        self.lbl_cols.setText(safe_tr("列数(&C):"))
        self.lbl_rows.setText(safe_tr("行数(&R):"))
        self.chk_merge_before_split.setText(safe_tr("拆分前合并单元格(&M)"))


class TableAutoFormatDialog(QDialog):
    """Table AutoFormat Styles gallery dialog (表格自动套用格式)."""

    STYLES = [
        "Table Normal",
        "Table Simple 1",
        "Table Simple 2",
        "Table Simple 3",
        "Table Classic 1",
        "Table Classic 2",
        "Table Classic 3",
        "Table Classic 4",
        "Table Colorful 1",
        "Table Colorful 2",
        "Table Colorful 3",
        "Table Columns 1",
        "Table Columns 2",
        "Table Grid 1",
        "Table Grid 2",
        "Table Grid 3",
        "Table Grid 4",
        "Table List 1",
        "Table List 2",
        "Table List 3",
        "Table Elegant",
        "Table Professional",
        "Table Contemporary",
    ]

    def __init__(self, current_style: str = "Table Grid 1", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("表格自动套用格式"))
        self.resize(500, 420)

        main_layout = QVBoxLayout(self)

        h_content = QHBoxLayout()

        # Left: Styles list
        v_list = QVBoxLayout()
        v_list.addWidget(QLabel(safe_tr("表格样式(&T):"), self))
        self.list_styles = QListWidget(self)
        for s in self.STYLES:
            item = QListWidgetItem(s)
            self.list_styles.addItem(item)
            if s == current_style:
                self.list_styles.setCurrentItem(item)
        if not self.list_styles.currentItem() and self.list_styles.count() > 0:
            self.list_styles.setCurrentRow(0)
        v_list.addWidget(self.list_styles)
        h_content.addLayout(v_list, 1)

        # Right: Live Preview
        v_prev = QVBoxLayout()
        v_prev.addWidget(QLabel(safe_tr("预览:"), self))
        self.preview_table = QTableWidget(4, 4, self)
        self.preview_table.setHorizontalHeaderLabels(["Jan", "Feb", "Mar", "Total"])
        self.preview_table.setVerticalHeaderLabels(["East", "West", "South", "Total"])
        sample_data = [
            ["10", "15", "20", "45"],
            ["12", "18", "24", "54"],
            ["14", "20", "28", "62"],
            ["36", "53", "72", "161"],
        ]
        for r in range(4):
            for c in range(4):
                self.preview_table.setItem(r, c, QTableWidgetItem(sample_data[r][c]))
        v_prev.addWidget(self.preview_table)
        h_content.addLayout(v_prev, 2)
        main_layout.addLayout(h_content)

        # Bottom options: Formats to apply & Special formats
        h_opts = QHBoxLayout()

        self.grp_apply = QGroupBox(safe_tr("要应用的格式"), self)
        l_apply = QVBoxLayout(self.grp_apply)
        self.chk_borders = QCheckBox(safe_tr("边框(&B)"), self.grp_apply)
        self.chk_shading = QCheckBox(safe_tr("底纹(&S)"), self.grp_apply)
        self.chk_font = QCheckBox(safe_tr("字体(&F)"), self.grp_apply)
        self.chk_color = QCheckBox(safe_tr("颜色(&C)"), self.grp_apply)
        self.chk_borders.setChecked(True)
        self.chk_shading.setChecked(True)
        self.chk_font.setChecked(True)
        self.chk_color.setChecked(True)
        l_apply.addWidget(self.chk_borders)
        l_apply.addWidget(self.chk_shading)
        l_apply.addWidget(self.chk_font)
        l_apply.addWidget(self.chk_color)
        h_opts.addWidget(self.grp_apply)

        self.grp_special = QGroupBox(safe_tr("将特殊格式应用于"), self)
        l_special = QVBoxLayout(self.grp_special)
        self.chk_heading_rows = QCheckBox(safe_tr("首行(&H)"), self.grp_special)
        self.chk_first_col = QCheckBox(safe_tr("首列(&I)"), self.grp_special)
        self.chk_last_row = QCheckBox(safe_tr("末行(&L)"), self.grp_special)
        self.chk_last_col = QCheckBox(safe_tr("末列(&A)"), self.grp_special)
        self.chk_heading_rows.setChecked(True)
        self.chk_first_col.setChecked(True)
        l_special.addWidget(self.chk_heading_rows)
        l_special.addWidget(self.chk_first_col)
        l_special.addWidget(self.chk_last_row)
        l_special.addWidget(self.chk_last_col)
        h_opts.addWidget(self.grp_special)

        main_layout.addLayout(h_opts)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def get_format_settings(self) -> dict[str, Any]:
        item = self.list_styles.currentItem()
        return {
            "style": item.text() if item else "Table Grid 1",
            "borders": self.chk_borders.isChecked(),
            "shading": self.chk_shading.isChecked(),
            "font": self.chk_font.isChecked(),
            "color": self.chk_color.isChecked(),
            "heading_rows": self.chk_heading_rows.isChecked(),
            "first_col": self.chk_first_col.isChecked(),
            "last_row": self.chk_last_row.isChecked(),
            "last_col": self.chk_last_col.isChecked(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("表格自动套用格式"))
        self.grp_apply.setTitle(safe_tr("要应用的格式"))
        self.chk_borders.setText(safe_tr("边框(&B)"))
        self.chk_shading.setText(safe_tr("底纹(&S)"))
        self.chk_font.setText(safe_tr("字体(&F)"))
        self.chk_color.setText(safe_tr("颜色(&C)"))
        self.grp_special.setTitle(safe_tr("将特殊格式应用于"))
        self.chk_heading_rows.setText(safe_tr("首行(&H)"))
        self.chk_first_col.setText(safe_tr("首列(&I)"))
        self.chk_last_row.setText(safe_tr("末行(&L)"))
        self.chk_last_col.setText(safe_tr("末列(&A)"))


class TableSortDialog(QDialog):
    """Sort Text or Table dialog with 3 sort tiers (排序)."""

    def __init__(self, column_count: int = 3, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("排序"))
        self.resize(360, 320)

        layout = QVBoxLayout(self)

        columns = [f"{safe_tr('列')} {i+1}" for i in range(max(1, column_count))]

        # Tier 1: Sort by
        self.grp_1 = QGroupBox(safe_tr("主要关键字"), self)
        l_1 = QHBoxLayout(self.grp_1)
        self.combo_col1 = QComboBox(self.grp_1)
        self.combo_col1.addItems(columns)
        self.combo_type1 = QComboBox(self.grp_1)
        self.combo_type1.addItems([safe_tr("笔划/拼音"), safe_tr("数字"), safe_tr("日期")])
        self.radio_asc1 = QRadioButton(safe_tr("升序(&A)"), self.grp_1)
        self.radio_desc1 = QRadioButton(safe_tr("降序(&D)"), self.grp_1)
        self.radio_asc1.setChecked(True)
        l_1.addWidget(self.combo_col1)
        l_1.addWidget(self.combo_type1)
        l_1.addWidget(self.radio_asc1)
        l_1.addWidget(self.radio_desc1)
        layout.addWidget(self.grp_1)

        # Tier 2: Then by
        self.grp_2 = QGroupBox(safe_tr("次要关键字"), self)
        l_2 = QHBoxLayout(self.grp_2)
        self.combo_col2 = QComboBox(self.grp_2)
        self.combo_col2.addItems([safe_tr("(无)")] + columns)
        self.combo_type2 = QComboBox(self.grp_2)
        self.combo_type2.addItems([safe_tr("笔划/拼音"), safe_tr("数字"), safe_tr("日期")])
        self.radio_asc2 = QRadioButton(safe_tr("升序(&S)"), self.grp_2)
        self.radio_desc2 = QRadioButton(safe_tr("降序(&E)"), self.grp_2)
        self.radio_asc2.setChecked(True)
        l_2.addWidget(self.combo_col2)
        l_2.addWidget(self.combo_type2)
        l_2.addWidget(self.radio_asc2)
        l_2.addWidget(self.radio_desc2)
        layout.addWidget(self.grp_2)

        # Tier 3: Then by
        self.grp_3 = QGroupBox(safe_tr("第三关键字"), self)
        l_3 = QHBoxLayout(self.grp_3)
        self.combo_col3 = QComboBox(self.grp_3)
        self.combo_col3.addItems([safe_tr("(无)")] + columns)
        self.combo_type3 = QComboBox(self.grp_3)
        self.combo_type3.addItems([safe_tr("笔划/拼音"), safe_tr("数字"), safe_tr("日期")])
        self.radio_asc3 = QRadioButton(safe_tr("升序(&C)"), self.grp_3)
        self.radio_desc3 = QRadioButton(safe_tr("降序(&N)"), self.grp_3)
        self.radio_asc3.setChecked(True)
        l_3.addWidget(self.combo_col3)
        l_3.addWidget(self.combo_type3)
        l_3.addWidget(self.radio_asc3)
        l_3.addWidget(self.radio_desc3)
        layout.addWidget(self.grp_3)

        # Header row options
        self.grp_hdr = QGroupBox(safe_tr("我的列表"), self)
        h_hdr = QHBoxLayout(self.grp_hdr)
        self.radio_has_header = QRadioButton(safe_tr("有标题行(&R)"), self.grp_hdr)
        self.radio_no_header = QRadioButton(safe_tr("无标题行(&O)"), self.grp_hdr)
        self.radio_has_header.setChecked(True)
        h_hdr.addWidget(self.radio_has_header)
        h_hdr.addWidget(self.radio_no_header)
        layout.addWidget(self.grp_hdr)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_sort_criteria(self) -> dict[str, Any]:
        return {
            "key1": {
                "column": self.combo_col1.currentIndex(),
                "type": self.combo_type1.currentText(),
                "ascending": self.radio_asc1.isChecked(),
            },
            "key2": {
                "column": self.combo_col2.currentIndex() - 1,
                "type": self.combo_type2.currentText(),
                "ascending": self.radio_asc2.isChecked(),
            },
            "key3": {
                "column": self.combo_col3.currentIndex() - 1,
                "type": self.combo_type3.currentText(),
                "ascending": self.radio_asc3.isChecked(),
            },
            "has_header": self.radio_has_header.isChecked(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("排序"))
        self.grp_1.setTitle(safe_tr("主要关键字"))
        self.grp_2.setTitle(safe_tr("次要关键字"))
        self.grp_3.setTitle(safe_tr("第三关键字"))
        self.grp_hdr.setTitle(safe_tr("我的列表"))
        self.radio_has_header.setText(safe_tr("有标题行(&R)"))
        self.radio_no_header.setText(safe_tr("无标题行(&O)"))


class TableFormulaDialog(QDialog):
    """Table Formula Calculation dialog (公式)."""

    def __init__(self, default_formula: str = "=SUM(ABOVE)", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("公式"))
        self.resize(340, 200)

        layout = QVBoxLayout(self)
        f_layout = QFormLayout()

        self.edit_formula = QLineEdit(default_formula, self)

        self.combo_format = QComboBox(self)
        self.combo_format.setEditable(True)
        self.combo_format.addItems([
            "0",
            "0.00",
            "#,##0",
            "#,##0.00",
            "$#,##0.00;($#,##0.00)",
            "0%",
            "0.00%",
        ])

        self.combo_function = QComboBox(self)
        self.combo_function.addItems([
            safe_tr("(粘贴函数)"),
            "ABS",
            "AND",
            "AVERAGE",
            "COUNT",
            "FALSE",
            "IF",
            "INT",
            "MAX",
            "MIN",
            "MOD",
            "NOT",
            "OR",
            "PRODUCT",
            "ROUND",
            "SIGN",
            "SUM",
            "TRUE",
        ])
        self.combo_function.currentIndexChanged.connect(self._on_function_selected)

        self.lbl_formula = QLabel(safe_tr("公式(&F):"), self)
        self.lbl_format = QLabel(safe_tr("数字格式(&N):"), self)
        self.lbl_function = QLabel(safe_tr("粘贴函数(&P):"), self)

        f_layout.addRow(self.lbl_formula, self.edit_formula)
        f_layout.addRow(self.lbl_format, self.combo_format)
        f_layout.addRow(self.lbl_function, self.combo_function)
        layout.addLayout(f_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _on_function_selected(self, index: int) -> None:
        if index > 0:
            fn = self.combo_function.itemText(index)
            cur = self.edit_formula.text().strip()
            if not cur or cur == "=":
                self.edit_formula.setText(f"={fn}()")
            else:
                self.edit_formula.setText(f"{cur}{fn}()")

    def get_formula_data(self) -> tuple[str, str]:
        return (self.edit_formula.text(), self.combo_format.currentText())

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("公式"))
        self.lbl_formula.setText(safe_tr("公式(&F):"))
        self.lbl_format.setText(safe_tr("数字格式(&N):"))
        self.lbl_function.setText(safe_tr("粘贴函数(&P):"))
