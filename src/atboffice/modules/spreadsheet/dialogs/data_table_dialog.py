"""Classic Excel 2003 Data Table (What-If Simulation) Dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import safe_tr

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


class DataTableDialog(QDialog):
    """Excel 2003 classic One-Input or Two-Input Data Table Dialog."""

    table_calculated = Signal(dict)

    def __init__(
        self,
        sheet_model: SheetDataModel | None = None,
        selected_range: tuple[int, int, int, int] | None = None,
        parent: QWidget | None = None,
        workbook_model: Any = None,
    ) -> None:
        super().__init__(parent)
        self.sheet_model = sheet_model
        self.workbook_model = workbook_model
        self.selected_range = selected_range or (0, 0, 5, 5)
        self.cells_written: int = 0

        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("模拟运算表"))
        self.setFixedWidth(340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Form grid
        form_grid = QGridLayout()
        form_grid.setVerticalSpacing(8)

        self.lbl_row = QLabel(safe_tr("输入引用行的单元格(&R):"), self)
        self.edit_row_input = QLineEdit(self)
        self.lbl_row.setBuddy(self.edit_row_input)
        form_grid.addWidget(self.lbl_row, 0, 0)
        form_grid.addWidget(self.edit_row_input, 0, 1)

        self.lbl_col = QLabel(safe_tr("输入引用列的单元格(&C):"), self)
        self.edit_col_input = QLineEdit(self)
        self.lbl_col.setBuddy(self.edit_col_input)
        form_grid.addWidget(self.lbl_col, 1, 0)
        form_grid.addWidget(self.edit_col_input, 1, 1)

        main_layout.addLayout(form_grid, 1)

        # Buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_ok = QPushButton(safe_tr("确定"), self)
        self.btn_cancel = QPushButton(safe_tr("取消"), self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch(1)

        main_layout.addLayout(btn_layout)

    def get_table_params(self) -> dict[str, str]:
        return {
            "row_input": self.edit_row_input.text().strip(),
            "col_input": self.edit_col_input.text().strip(),
        }

    def _on_ok(self) -> None:
        params = self.get_table_params()
        row_input = params["row_input"]
        col_input = params["col_input"]

        if not row_input and not col_input:
            QMessageBox.warning(
                self,
                safe_tr("错误"),
                safe_tr("必须指定行输入单元格或列输入单元格。"),
            )
            return

        # Substitute each input value, recalculate the dependency graph and capture
        # the formula result (Excel's {=TABLE(row, col)} semantics).
        if self.sheet_model is not None and self.selected_range:
            from atboffice.modules.spreadsheet.tools.data_tools import compute_data_table

            try:
                self.cells_written = compute_data_table(
                    self.workbook_model,
                    self.sheet_model,
                    self.selected_range,
                    row_input,
                    col_input,
                )
            except ValueError as exc:
                QMessageBox.warning(self, safe_tr("模拟运算表"), str(exc))
                return

        self.table_calculated.emit(params)
        self.accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("模拟运算表"))
        self.lbl_row.setText(safe_tr("输入引用行的单元格(&R):"))
        self.lbl_col.setText(safe_tr("输入引用列的单元格(&C):"))
        self.btn_ok.setText(safe_tr("确定"))
        self.btn_cancel.setText(safe_tr("取消"))
