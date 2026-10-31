"""AutoFilter drop-down menu and condition dialogs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.calc.references import col_name
from atboffice.modules.spreadsheet.dialogs.custom_filter import CustomFilterDialog
from atboffice.modules.spreadsheet.models.filter_model import (
    AutoFilter,
    ColumnFilter,
    is_blank,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("FilterDropdown", text)


class Top10FilterDialog(QDialog):
    """Excel 2003 classic Top 10 AutoFilter dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("Top 10 AutoFilter"))
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)

        self.label_show = QLabel(safe_tr("Show"), self)
        layout.addWidget(self.label_show)

        h_layout = QHBoxLayout()
        self.combo_top_bottom = QComboBox(self)
        self.combo_top_bottom.addItem(safe_tr("Top"), True)
        self.combo_top_bottom.addItem(safe_tr("Bottom"), False)
        h_layout.addWidget(self.combo_top_bottom)

        self.spin_count = QSpinBox(self)
        self.spin_count.setRange(1, 500)
        self.spin_count.setValue(10)
        h_layout.addWidget(self.spin_count)

        self.combo_kind = QComboBox(self)
        self.combo_kind.addItem(safe_tr("Items"), False)
        self.combo_kind.addItem(safe_tr("Percent"), True)
        h_layout.addWidget(self.combo_kind)

        layout.addLayout(h_layout)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_criteria(self) -> tuple[bool, int, bool]:
        """Return (is_top, count, is_percent)."""
        is_top = bool(self.combo_top_bottom.currentData())
        count = self.spin_count.value()
        is_percent = bool(self.combo_kind.currentData())
        return (is_top, count, is_percent)


class FilterDropdown(QWidget):
    """Popup drop-down widget for AutoFilter with quick sort, top 10, custom, and checkable list."""

    filter_applied = Signal(object)  # ColumnFilter
    filter_cleared = Signal()
    sort_requested = Signal(bool)  # desc

    def __init__(
        self,
        model: SheetDataModel,
        af: AutoFilter,
        col: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self.model = model
        self.af = af
        self.col = col
        self.col_offset = col - af.c1

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setStyleSheet(
            """
            FilterDropdown {
                background-color: #ECE9D8;
                border: 1px solid #7F9DB9;
                font-family: Arial, sans-serif;
                font-size: 12px;
            }
            QPushButton.action-btn {
                text-align: left;
                padding: 4px 8px;
                border: none;
                background: transparent;
            }
            QPushButton.action-btn:hover {
                background-color: #316AC5;
                color: white;
            }
            QListWidget {
                background: white;
                border: 1px solid #7F9DB9;
            }
            """
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        # 1. Action Items
        self.btn_sort_asc = QPushButton(safe_tr("(Sort Ascending)"), self)
        self.btn_sort_asc.setProperty("class", "action-btn")
        self.btn_sort_asc.clicked.connect(self._on_sort_asc)
        main_layout.addWidget(self.btn_sort_asc)

        self.btn_sort_desc = QPushButton(safe_tr("(Sort Descending)"), self)
        self.btn_sort_desc.setProperty("class", "action-btn")
        self.btn_sort_desc.clicked.connect(self._on_sort_desc)
        main_layout.addWidget(self.btn_sort_desc)

        # Separator line
        sep1 = QFrame(self)
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(sep1)

        self.btn_all = QPushButton(safe_tr("(All)"), self)
        self.btn_all.setProperty("class", "action-btn")
        self.btn_all.clicked.connect(self._on_all)
        main_layout.addWidget(self.btn_all)

        self.btn_top10 = QPushButton(safe_tr("(Top 10...)"), self)
        self.btn_top10.setProperty("class", "action-btn")
        self.btn_top10.clicked.connect(self._on_top10)
        main_layout.addWidget(self.btn_top10)

        self.btn_custom = QPushButton(safe_tr("(Custom...)"), self)
        self.btn_custom.setProperty("class", "action-btn")
        self.btn_custom.clicked.connect(self._on_custom)
        main_layout.addWidget(self.btn_custom)

        # Separator line
        sep2 = QFrame(self)
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(sep2)

        # 2. Checkable unique values list
        self.list_widget = QListWidget(self)
        self.list_widget.setFixedHeight(160)
        main_layout.addWidget(self.list_widget)

        # Extract unique values
        self.unique_values, self.has_blanks = self._extract_unique_values()

        # Item: (Select All)
        self.item_select_all = QListWidgetItem(safe_tr("(Select All)"))
        self.item_select_all.setFlags(
            self.item_select_all.flags() | Qt.ItemFlag.ItemIsUserCheckable
        )
        self.item_select_all.setCheckState(Qt.CheckState.Checked)
        self.list_widget.addItem(self.item_select_all)

        # Unique value items
        current_crit = self.af.cols.get(self.col_offset)
        cur_val_set = (
            {str(x).lower() for x in current_crit.values}
            if (current_crit and current_crit.values is not None)
            else None
        )

        self.value_items: list[tuple[QListWidgetItem, str]] = []
        for val_str in self.unique_values:
            item = QListWidgetItem(val_str)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = (
                True
                if cur_val_set is None
                else (val_str.lower() in cur_val_set)
            )
            item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
            self.list_widget.addItem(item)
            self.value_items.append((item, val_str))

        # Blank item if any
        self.blank_item: QListWidgetItem | None = None
        if self.has_blanks:
            self.blank_item = QListWidgetItem(safe_tr("(Blanks)"))
            self.blank_item.setFlags(
                self.blank_item.flags() | Qt.ItemFlag.ItemIsUserCheckable
            )
            checked = True if cur_val_set is None else bool(current_crit and current_crit.blank)
            self.blank_item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
            self.list_widget.addItem(self.blank_item)

        self.list_widget.itemChanged.connect(self._on_item_changed)

        # 3. Bottom OK / Cancel buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(4, 4, 4, 4)
        self.btn_ok = QPushButton(safe_tr("OK"), self)
        self.btn_ok.clicked.connect(self._on_apply_checked)
        self.btn_cancel = QPushButton(safe_tr("Cancel"), self)
        self.btn_cancel.clicked.connect(self.close)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_layout)

        self.setMinimumWidth(180)
        self._updating_checks = False

    def _extract_unique_values(self) -> tuple[list[str], bool]:
        """Extract unique displayed cell texts and presence of blanks in this column."""
        seen = set()
        unique: list[str] = []
        has_blanks = False

        for r in range(self.af.r1 + 1, self.af.r2 + 1):
            val = self.model.get_cell_value(r, self.col)
            text = self.model.get_formatted_text(r, self.col)
            if is_blank(val) or not text.strip():
                has_blanks = True
            else:
                if text not in seen:
                    seen.add(text)
                    unique.append(text)

        unique.sort()
        return unique, has_blanks

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._updating_checks:
            return
        self._updating_checks = True

        if item == self.item_select_all:
            state = self.item_select_all.checkState()
            for v_item, _ in self.value_items:
                v_item.setCheckState(state)
            if self.blank_item is not None:
                self.blank_item.setCheckState(state)
        else:
            # Check if all are checked
            all_checked = all(
                v_item.checkState() == Qt.CheckState.Checked
                for v_item, _ in self.value_items
            )
            if self.blank_item is not None:
                all_checked = all_checked and (
                    self.blank_item.checkState() == Qt.CheckState.Checked
                )

            self.item_select_all.setCheckState(
                Qt.CheckState.Checked if all_checked else Qt.CheckState.Unchecked
            )

        self._updating_checks = False

    def _on_sort_asc(self) -> None:
        self.sort_requested.emit(False)
        self.close()

    def _on_sort_desc(self) -> None:
        self.sort_requested.emit(True)
        self.close()

    def _on_all(self) -> None:
        self.filter_cleared.emit()
        self.close()

    def _on_top10(self) -> None:
        self.hide()
        dlg = Top10FilterDialog(self.parentWidget())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            is_top, count, is_percent = dlg.get_criteria()
            crit = ColumnFilter(
                top10_top=is_top,
                top10_val=count,
                top10_percent=is_percent,
            )
            self.filter_applied.emit(crit)
        self.close()

    def _on_custom(self) -> None:
        self.hide()
        header_text = self.model.get_formatted_text(self.af.r1, self.col)
        if not header_text.strip():
            header_text = col_name(self.col)

        current_crit = self.af.cols.get(self.col_offset)
        initial_conds = current_crit.custom_list if current_crit else None
        initial_and = current_crit.custom_and if current_crit else True

        dlg = CustomFilterDialog(
            column_header=header_text,
            unique_values=self.unique_values,
            initial_conditions=initial_conds,
            initial_and=initial_and,
            parent=self.parentWidget(),
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            conds, is_and = dlg.get_custom_criteria()
            if conds:
                crit = ColumnFilter(
                    custom_list=conds,
                    custom_and=is_and,
                )
                self.filter_applied.emit(crit)
            elif current_crit and current_crit.custom_list:
                self.filter_cleared.emit()
        self.close()

    def _on_apply_checked(self) -> None:
        # If select all is checked, it's equivalent to clearing filter for this column
        if self.item_select_all.checkState() == Qt.CheckState.Checked:
            self.filter_cleared.emit()
            self.close()
            return

        selected_values = {
            val_str
            for v_item, val_str in self.value_items
            if v_item.checkState() == Qt.CheckState.Checked
        }
        blank_selected = bool(
            self.blank_item is not None
            and self.blank_item.checkState() == Qt.CheckState.Checked
        )

        crit = ColumnFilter(
            values=selected_values,
            blank=blank_selected,
        )
        self.filter_applied.emit(crit)
        self.close()
