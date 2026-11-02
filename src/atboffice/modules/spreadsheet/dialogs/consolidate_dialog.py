"""Classic Excel 2003 Consolidate Dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


def safe_tr(text: str) -> str:
    """Safely translate ConsolidateDialog UI string."""
    return QCoreApplication.translate("ConsolidateDialog", text)


CONSOLIDATE_FUNCTIONS = [
    ("SUM", "求和", "Sum"),
    ("COUNT", "计数", "Count"),
    ("AVERAGE", "平均值", "Average"),
    ("MAX", "最大值", "Max"),
    ("MIN", "最小值", "Min"),
    ("PRODUCT", "乘积", "Product"),
    ("COUNTNUMS", "数值计数", "Count Numbers"),
    ("STDEV", "标准偏差", "StdDev"),
    ("VAR", "方差", "Var"),
]


class ConsolidateDialog(QDialog):
    """Excel 2003 classic Consolidate Dialog."""

    consolidate_applied = Signal(dict)

    def __init__(
        self,
        sheet_model: SheetDataModel | None = None,
        workbook_model: WorkbookModel | None = None,
        initial_references: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sheet_model = sheet_model
        self.workbook_model = workbook_model
        self.references: list[str] = list(initial_references or [])

        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("合并计算"))
        self.resize(380, 360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Left area
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)

        left_layout.addWidget(QLabel(safe_tr("函数(&F):"), self))
        self.combo_function = QComboBox(self)
        for fn in CONSOLIDATE_FUNCTIONS:
            self.combo_function.addItem(f"{fn[1]} ({fn[2]})", fn[0])
        left_layout.addWidget(self.combo_function)

        left_layout.addWidget(QLabel(safe_tr("引用位置(&R):"), self))
        self.edit_reference = QLineEdit(self)
        left_layout.addWidget(self.edit_reference)

        left_layout.addWidget(QLabel(safe_tr("所有引用位置(&A):"), self))
        self.list_references = QListWidget(self)
        for ref in self.references:
            self.list_references.addItem(ref)
        left_layout.addWidget(self.list_references, 1)

        # Label positions
        grp_labels = QGroupBox(safe_tr("标签位置:"), self)
        v_lbl = QVBoxLayout(grp_labels)
        self.check_top_row = QCheckBox(safe_tr("首行(&T)"), grp_labels)
        self.check_left_col = QCheckBox(safe_tr("最左列(&L)"), grp_labels)
        v_lbl.addWidget(self.check_top_row)
        v_lbl.addWidget(self.check_left_col)
        left_layout.addWidget(grp_labels)

        self.check_links = QCheckBox(safe_tr("创建指向源数据的链接(&S)"), self)
        left_layout.addWidget(self.check_links)

        main_layout.addLayout(left_layout, 1)

        # Right buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_ok = QPushButton(safe_tr("确定"), self)
        self.btn_close = QPushButton(safe_tr("关闭"), self)
        self.btn_add = QPushButton(safe_tr("添加(&A)"), self)
        self.btn_delete = QPushButton(safe_tr("删除(&D)"), self)
        self.btn_browse = QPushButton(safe_tr("浏览(&B)..."), self)

        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_close.clicked.connect(self.reject)
        self.btn_add.clicked.connect(self._on_add_reference)
        self.btn_delete.clicked.connect(self._on_delete_reference)

        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_close)
        btn_layout.addSpacing(8)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_browse)
        btn_layout.addStretch(1)

        main_layout.addLayout(btn_layout)

    def _on_add_reference(self) -> None:
        ref = self.edit_reference.text().strip()
        existing = [
            self.list_references.item(i).text() for i in range(self.list_references.count())
        ]
        if ref and ref not in existing:
            self.list_references.addItem(ref)
            self.edit_reference.clear()

    def _on_delete_reference(self) -> None:
        row = self.list_references.currentRow()
        if row >= 0:
            self.list_references.takeItem(row)

    def get_consolidation_config(self) -> dict[str, Any]:
        """Extract user configuration."""
        refs = [self.list_references.item(i).text() for i in range(self.list_references.count())]
        return {
            "function": self.combo_function.currentData(),
            "references": refs,
            "top_row": self.check_top_row.isChecked(),
            "left_column": self.check_left_col.isChecked(),
            "create_links": self.check_links.isChecked(),
        }

    def _on_ok(self) -> None:
        cfg = self.get_consolidation_config()
        self.consolidate_applied.emit(cfg)
        self.accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("合并计算"))
        self.btn_ok.setText(safe_tr("确定"))
        self.btn_close.setText(safe_tr("关闭"))
        self.btn_add.setText(safe_tr("添加(&A)"))
        self.btn_delete.setText(safe_tr("删除(&D)"))
        self.btn_browse.setText(safe_tr("浏览(&B)..."))
        self.check_top_row.setText(safe_tr("首行(&T)"))
        self.check_left_col.setText(safe_tr("最左列(&L)"))
        self.check_links.setText(safe_tr("创建指向源数据的链接(&S)"))
