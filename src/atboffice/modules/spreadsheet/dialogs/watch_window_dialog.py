"""Excel 2003 classic Watch Window dialog for monitoring cell formulas and values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.calc.references import cell_name

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("WatchWindowDialog", text)


@dataclass(frozen=True)
class WatchItem:
    """Entry describing a watched cell location."""

    book: str
    sheet: str
    r: int
    c: int
    name: str = ""


class WatchWindowDialog(QDialog):
    """Modeless dialog displaying a persistent table of watched cells."""

    navigate_requested = Signal(str, int, int)  # (sheet_name, row, col)
    add_watch_requested = Signal()

    def __init__(
        self,
        workbook: WorkbookModel | None = None,
        book_name: str = "Book1",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.workbook = workbook
        self.book_name = book_name
        self._watches: list[WatchItem] = []

        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("监视窗口"))
        self.resize(540, 260)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # Top action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_add = QPushButton(safe_tr("添加监视(&A)..."), self)
        self.btn_add.clicked.connect(self._on_add_clicked)
        btn_layout.addWidget(self.btn_add)

        self.btn_delete = QPushButton(safe_tr("删除监视(&D)"), self)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        btn_layout.addWidget(self.btn_delete)

        btn_layout.addStretch()

        self.btn_close = QPushButton(safe_tr("关闭(&C)"), self)
        self.btn_close.clicked.connect(self.hide)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        # Watch Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                safe_tr("工作簿"),
                safe_tr("工作表"),
                safe_tr("名称"),
                safe_tr("单元格"),
                safe_tr("值"),
                safe_tr("公式"),
            ]
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.table)

    def add_watch(
        self,
        sheet_name: str,
        r: int,
        c: int,
        book_name: str | None = None,
        name: str = "",
    ) -> bool:
        """Add a cell to the watch list if not already present."""
        bname = book_name or self.book_name
        item = WatchItem(book=bname, sheet=sheet_name, r=r, c=c, name=name)
        if item in self._watches:
            return False

        self._watches.append(item)
        self.refresh_watches()
        return True

    def delete_selected_watch(self) -> None:
        """Remove the currently highlighted watch entry."""
        row = self.table.currentRow()
        if 0 <= row < len(self._watches):
            self._watches.pop(row)
            self.refresh_watches()

    def refresh_watches(self) -> None:
        """Refresh table rows with current cell values and formulas from workbook."""
        self.table.setRowCount(len(self._watches))

        for idx, w in enumerate(self._watches):
            val_str = ""
            formula_str = ""

            sheet = self._get_sheet(w.sheet)
            if sheet is not None:
                cell = sheet.get_cell(w.r, w.c)
                if cell is not None:
                    if cell.value is not None:
                        val_str = str(cell.value)
                    if cell.formula:
                        formula_str = (
                            cell.formula
                            if cell.formula.startswith("=")
                            else f"={cell.formula}"
                        )

            cell_ref_str = cell_name(w.r, w.c, ra=True, ca=True)

            item_book = QTableWidgetItem(w.book)
            item_sheet = QTableWidgetItem(w.sheet)
            item_name = QTableWidgetItem(w.name)
            item_cell = QTableWidgetItem(cell_ref_str)
            item_val = QTableWidgetItem(val_str)
            item_formula = QTableWidgetItem(formula_str)

            for col, item in enumerate(
                [
                    item_book,
                    item_sheet,
                    item_name,
                    item_cell,
                    item_val,
                    item_formula,
                ]
            ):
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                self.table.setItem(idx, col, item)

    def _get_sheet(self, sheet_name: str) -> Any | None:
        if self.workbook:
            for s in self.workbook.sheets:
                if s.name == sheet_name:
                    return s
        return None

    def _on_add_clicked(self) -> None:
        self.add_watch_requested.emit()

    def _on_delete_clicked(self) -> None:
        self.delete_selected_watch()

    def _on_item_double_clicked(self, item: QTableWidgetItem) -> None:
        row = item.row()
        if 0 <= row < len(self._watches):
            w = self._watches[row]
            self.navigate_requested.emit(w.sheet, w.r, w.c)
