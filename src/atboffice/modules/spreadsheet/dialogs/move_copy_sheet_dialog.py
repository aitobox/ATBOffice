"""Excel 2003 Move or Copy Sheet dialog for Ledger workbook management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


def safe_tr(text: str) -> str:
    """Translate UI text safely for MoveCopySheetDialog."""
    return QCoreApplication.translate("MoveCopySheetDialog", text)


class MoveCopySheetDialog(QDialog):
    """Dialog allowing user to move or duplicate worksheets within the workbook."""

    def __init__(
        self,
        workbook: WorkbookModel,
        active_index: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.workbook = workbook
        self.active_index = active_index

        self.setWindowTitle(safe_tr("移动或复制工作表"))
        self.setFixedSize(300, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Label: before sheet
        self.lbl_target = QLabel(safe_tr("下列选定工作表之前(&B):"), self)
        layout.addWidget(self.lbl_target)

        # List of sheets
        self.list_sheets = QListWidget(self)
        for sheet in self.workbook.sheets:
            self.list_sheets.addItem(sheet.name)
        self.list_sheets.addItem(safe_tr("(移至最后)"))

        if 0 <= self.active_index < self.list_sheets.count():
            self.list_sheets.setCurrentRow(self.active_index)
        else:
            self.list_sheets.setCurrentRow(0)
        layout.addWidget(self.list_sheets)

        # Checkbox: Create a copy
        self.chk_copy = QCheckBox(safe_tr("建立副本(&C)"), self)
        layout.addWidget(self.chk_copy)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    @property
    def selected_target_index(self) -> int:
        """Selected sheet target index (0 .. len(sheets), where len(sheets) is end)."""
        row = self.list_sheets.currentRow()
        sheet_count = len(self.workbook.sheets)
        if row < 0 or row >= sheet_count:
            return sheet_count
        return row

    @property
    def is_create_copy(self) -> bool:
        """Whether the user chose to create a copy rather than move."""
        return self.chk_copy.isChecked()

    def retranslate_ui(self) -> None:
        """Retranslate dialog text."""
        self.setWindowTitle(safe_tr("移动或复制工作表"))
        self.lbl_target.setText(safe_tr("下列选定工作表之前(&B):"))
        self.chk_copy.setText(safe_tr("建立副本(&C)"))
        count = self.list_sheets.count()
        sheet_count = len(self.workbook.sheets)
        if count > sheet_count:
            last_item = self.list_sheets.item(count - 1)
            if last_item is not None:
                last_item.setText(safe_tr("(移至最后)"))
