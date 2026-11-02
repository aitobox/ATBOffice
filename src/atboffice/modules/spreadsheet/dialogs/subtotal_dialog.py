"""Classic Excel 2003 Subtotal Calculation Dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


def safe_tr(text: str) -> str:
    """Safely translate SubtotalDialog UI string."""
    return QCoreApplication.translate("SubtotalDialog", text)


SUBTOTAL_FUNCTIONS = [
    ("SUM", 9, "求和", "Sum"),
    ("COUNT", 2, "计数", "Count"),
    ("AVERAGE", 1, "平均值", "Average"),
    ("MAX", 4, "最大值", "Max"),
    ("MIN", 5, "最小值", "Min"),
    ("PRODUCT", 6, "乘积", "Product"),
    ("COUNTNUMS", 2, "数值计数", "Count Numbers"),
    ("STDEV", 7, "标准偏差", "StdDev"),
    ("VAR", 10, "方差", "Var"),
]


class SubtotalDialog(QDialog):
    """Excel 2003 classic Subtotal calculation dialog."""

    subtotal_applied = Signal(dict)
    subtotal_removed = Signal()

    def __init__(
        self,
        sheet_model: SheetDataModel | None = None,
        selected_range: tuple[int, int, int, int] | None = None,
        headers: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sheet_model = sheet_model
        self.selected_range = selected_range or (0, 0, 10, 5)
        self.headers = headers or []

        # If headers not provided, infer from sheet_model top row
        if not self.headers and sheet_model is not None:
            r1, c1, _, c2 = self.selected_range
            self.headers = [
                str(sheet_model.get_cell_value(r1, c) or f"Column {c + 1}")
                for c in range(c1, c2 + 1)
            ]
        if not self.headers:
            self.headers = ["ID", "Name", "Category", "Amount", "Quantity"]

        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("分类汇总"))
        self.resize(340, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Left options area
        left_layout = QVBoxLayout()
        left_layout.setSpacing(6)

        left_layout.addWidget(QLabel(safe_tr("分类字段(&A):"), self))
        self.combo_group_by = QComboBox(self)
        self.combo_group_by.addItems(self.headers)
        left_layout.addWidget(self.combo_group_by)

        left_layout.addWidget(QLabel(safe_tr("使用函数(&U):"), self))
        self.combo_function = QComboBox(self)
        for fn in SUBTOTAL_FUNCTIONS:
            self.combo_function.addItem(f"{fn[2]} ({fn[3]})", fn[1])
        left_layout.addWidget(self.combo_function)

        left_layout.addWidget(QLabel(safe_tr("选定汇总项(&D):"), self))
        self.list_columns = QListWidget(self)
        for idx, h in enumerate(self.headers):
            item = QListWidgetItem(h, self.list_columns)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            # Default check the last column
            item.setCheckState(Qt.CheckState.Checked if idx == len(self.headers) - 1 else Qt.CheckState.Unchecked)
        left_layout.addWidget(self.list_columns, 1)

        self.check_replace = QCheckBox(safe_tr("替换当前分类汇总(&R)"), self)
        self.check_replace.setChecked(True)
        left_layout.addWidget(self.check_replace)

        self.check_page_break = QCheckBox(safe_tr("每组数据分页(&P)"), self)
        self.check_page_break.setChecked(False)
        left_layout.addWidget(self.check_page_break)

        self.check_summary_below = QCheckBox(safe_tr("汇总结果显示在数据下方(&S)"), self)
        self.check_summary_below.setChecked(True)
        left_layout.addWidget(self.check_summary_below)

        main_layout.addLayout(left_layout, 1)

        # Right buttons area
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_ok = QPushButton(safe_tr("确定"), self)
        self.btn_cancel = QPushButton(safe_tr("取消"), self)
        self.btn_remove_all = QPushButton(safe_tr("全部删除(&A)"), self)

        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_remove_all.clicked.connect(self._on_remove_all)

        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_remove_all)
        btn_layout.addStretch(1)

        main_layout.addLayout(btn_layout)

    def get_subtotal_config(self) -> dict[str, Any]:
        """Extract subtotal configuration."""
        selected_cols = []
        for i in range(self.list_columns.count()):
            item = self.list_columns.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_cols.append(i)

        fn_code = self.combo_function.currentData()
        return {
            "group_by_col": self.combo_group_by.currentIndex(),
            "group_by_name": self.combo_group_by.currentText(),
            "function_code": fn_code,
            "function_name": self.combo_function.currentText(),
            "subtotal_cols": selected_cols,
            "replace_current": self.check_replace.isChecked(),
            "page_break": self.check_page_break.isChecked(),
            "summary_below": self.check_summary_below.isChecked(),
        }

    def _on_ok(self) -> None:
        cfg = self.get_subtotal_config()
        self.subtotal_applied.emit(cfg)
        self.accept()

    def _on_remove_all(self) -> None:
        self.subtotal_removed.emit()
        self.accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("分类汇总"))
        self.check_replace.setText(safe_tr("替换当前分类汇总(&R)"))
        self.check_page_break.setText(safe_tr("每组数据分页(&P)"))
        self.check_summary_below.setText(safe_tr("汇总结果显示在数据下方(&S)"))
        self.btn_ok.setText(safe_tr("确定"))
        self.btn_cancel.setText(safe_tr("取消"))
        self.btn_remove_all.setText(safe_tr("全部删除(&A)"))
