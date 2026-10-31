"""Excel 2003 classic PivotTable and PivotChart Wizard Dialog.

Replicates dialogs2.js: D.pivotTable, providing field configuration,
aggregation selection, destination choice, and interactive generation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.calc.references import (
    abs_range_name,
    col_name,
    parse_cell,
    parse_range,
    quote_sheet,
)
from atboffice.modules.spreadsheet.models.pivot_model import (
    PivotConfig,
    build_pivot_table,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


def safe_tr(text: str) -> str:
    """Translate UI text safely for PivotTableWizardDialog."""
    return QCoreApplication.translate("PivotTableWizardDialog", text)


PIV_FUNCTIONS: list[tuple[str, str]] = [
    ("sum", "求和 (Sum)"),
    ("count", "计数 (Count)"),
    ("average", "平均值 (Average)"),
    ("max", "最大值 (Max)"),
    ("min", "最小值 (Min)"),
    ("countNums", "数值计数 (Count Nums)"),
]


class PivotTableWizardDialog(QDialog):
    """Excel 2003 classic PivotTable Wizard dialog."""

    def __init__(
        self,
        workbook: WorkbookModel,
        initial_sheet_name: str,
        initial_range: tuple[int, int, int, int],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.workbook = workbook
        self.sheet_name = initial_sheet_name
        self.r1, self.c1, self.r2, self.c2 = initial_range

        self.created_sheet: SheetDataModel | None = None
        self.result_bbox: tuple[int, int, int, int] | None = None

        self.setWindowTitle(safe_tr("数据透视表和数据透视图向导"))
        self.resize(460, 420)
        self.setModal(True)

        self._init_ui()
        self._populate_fields_from_range()
        self.retranslate_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # 1. Source Data Range
        range_layout = QHBoxLayout()
        self.lbl_range = QLabel(self)
        range_layout.addWidget(self.lbl_range)

        default_ref = f"{quote_sheet(self.sheet_name)}!{abs_range_name({'r1': self.r1, 'c1': self.c1, 'r2': self.r2, 'c2': self.c2})}"
        self.edit_range = QLineEdit(default_ref, self)
        self.edit_range.editingFinished.connect(self._on_range_edited)
        range_layout.addWidget(self.edit_range)
        main_layout.addLayout(range_layout)

        # 2. Field Layout GroupBox
        self.group_layout = QGroupBox(self)
        layout_grid = QVBoxLayout(self.group_layout)
        layout_grid.setSpacing(8)

        # Row Field
        row_box = QHBoxLayout()
        self.lbl_row = QLabel(self)
        self.combo_row = QComboBox(self.group_layout)
        row_box.addWidget(self.lbl_row, stretch=1)
        row_box.addWidget(self.combo_row, stretch=2)
        layout_grid.addLayout(row_box)

        # Column Field (optional)
        col_box = QHBoxLayout()
        self.lbl_col = QLabel(self)
        self.combo_col = QComboBox(self.group_layout)
        col_box.addWidget(self.lbl_col, stretch=1)
        col_box.addWidget(self.combo_col, stretch=2)
        layout_grid.addLayout(col_box)

        # Data Field + Summarize By
        data_box = QHBoxLayout()
        self.lbl_data = QLabel(self)
        self.combo_data = QComboBox(self.group_layout)
        self.lbl_fn = QLabel(self)
        self.combo_fn = QComboBox(self.group_layout)
        for fn_code, fn_name in PIV_FUNCTIONS:
            self.combo_fn.addItem(fn_name, fn_code)
        data_box.addWidget(self.lbl_data)
        data_box.addWidget(self.combo_data, stretch=1)
        data_box.addWidget(self.lbl_fn)
        data_box.addWidget(self.combo_fn, stretch=1)
        layout_grid.addLayout(data_box)

        # Page / Filter Field
        page_box = QHBoxLayout()
        self.lbl_page = QLabel(self)
        self.combo_page = QComboBox(self.group_layout)
        page_box.addWidget(self.lbl_page, stretch=1)
        page_box.addWidget(self.combo_page, stretch=2)
        layout_grid.addLayout(page_box)

        main_layout.addWidget(self.group_layout)

        # 3. Location GroupBox
        self.group_location = QGroupBox(self)
        loc_vbox = QVBoxLayout(self.group_location)
        self.radio_new_sheet = QRadioButton(self.group_location)
        self.radio_existing_sheet = QRadioButton(self.group_location)
        self.radio_new_sheet.setChecked(True)

        self.loc_btn_group = QButtonGroup(self.group_location)
        self.loc_btn_group.addButton(self.radio_new_sheet)
        self.loc_btn_group.addButton(self.radio_existing_sheet)

        loc_vbox.addWidget(self.radio_new_sheet)
        loc_vbox.addWidget(self.radio_existing_sheet)
        main_layout.addWidget(self.group_location)

        # 4. Hint Label
        self.lbl_hint = QLabel(self)
        self.lbl_hint.setWordWrap(True)
        self.lbl_hint.setStyleSheet("color: #666; font-size: 11px;")
        main_layout.addWidget(self.lbl_hint)

        # 5. Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        self.btn_finish = self.button_box.button(QDialogButtonBox.Ok)
        self.btn_cancel = self.button_box.button(QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._on_finish)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def retranslate_ui(self) -> None:
        """Apply vivid, localized strings for 100% i18n coverage."""
        self.setWindowTitle(safe_tr("数据透视表和数据透视图向导"))
        self.lbl_range.setText(safe_tr("选定区域(&R):"))
        self.group_layout.setTitle(safe_tr("字段布局(&L)"))
        self.lbl_row.setText(safe_tr("行字段(&R):"))
        self.lbl_col.setText(safe_tr("列字段(&C):"))
        self.lbl_data.setText(safe_tr("数据字段(&D):"))
        self.lbl_fn.setText(safe_tr("汇总方式(&S):"))
        self.lbl_page.setText(safe_tr("页字段(&P):"))
        self.group_location.setTitle(
            safe_tr("选择放置数据透视表的位置")
        )
        self.radio_new_sheet.setText(safe_tr("新工作表(&N)"))
        self.radio_existing_sheet.setText(
            safe_tr("现有工作表 (位于当前单元格)(&E)")
        )
        self.lbl_hint.setText(
            safe_tr(
                "Ledger 将生成格式化的交叉汇总报表；源数据变动后可重新生成。"
            )
        )
        if self.btn_finish:
            self.btn_finish.setText(safe_tr("完成(&F)"))
        if self.btn_cancel:
            self.btn_cancel.setText(safe_tr("取消(&C)"))

    def _parse_range_input(self) -> bool:
        """Parse text from range input line edit."""
        text = self.edit_range.text().strip()
        if not text:
            return False

        sheet_part = self.sheet_name
        ref_part = text
        if "!" in text:
            sheet_part, ref_part = text.split("!", 1)
            sheet_part = sheet_part.strip().strip("'")

        parsed = parse_range(ref_part)
        if not parsed:
            return False

        self.sheet_name = sheet_part
        self.r1, self.c1, self.r2, self.c2 = (
            parsed["r1"],
            parsed["c1"],
            parsed["r2"],
            parsed["c2"],
        )
        return True

    def _on_range_edited(self) -> None:
        """Reload fields when user modifies range text."""
        if self._parse_range_input():
            self._populate_fields_from_range()

    def _populate_fields_from_range(self) -> None:
        """Populate ComboBox dropdowns based on column headers in source range."""
        src_sheet = self.workbook.get_sheet_by_name(self.sheet_name)
        if not src_sheet:
            return

        self.combo_row.clear()
        self.combo_col.clear()
        self.combo_data.clear()
        self.combo_page.clear()

        self.combo_col.addItem(safe_tr("(无)"), None)
        self.combo_page.addItem(safe_tr("(全部)"), None)

        numeric_col: int | None = None
        for col_idx in range(self.c1, self.c2 + 1):
            val = src_sheet.get_cell_value(self.r1, col_idx)
            header_text = (
                str(val) if val is not None and str(val).strip() else col_name(col_idx)
            )

            self.combo_row.addItem(header_text, col_idx)
            self.combo_col.addItem(header_text, col_idx)
            self.combo_data.addItem(header_text, col_idx)
            self.combo_page.addItem(header_text, col_idx)

            # Check if second row has numeric value to suggest data column
            if numeric_col is None and self.r2 > self.r1:
                sample_val = src_sheet.get_cell_value(self.r1 + 1, col_idx)
                if isinstance(sample_val, (int, float)) and not isinstance(sample_val, bool):
                    numeric_col = col_idx

        # Intelligent defaults
        if self.combo_row.count() > 0:
            self.combo_row.setCurrentIndex(0)

        if numeric_col is not None:
            # Set data field to numeric column
            for i in range(self.combo_data.count()):
                if self.combo_data.itemData(i) == numeric_col:
                    self.combo_data.setCurrentIndex(i)
                    break
            self.combo_fn.setCurrentIndex(0)  # "sum"
        else:
            if self.combo_data.count() > 0:
                self.combo_data.setCurrentIndex(self.combo_data.count() - 1)
            self.combo_fn.setCurrentIndex(1)  # "count"

    def _on_finish(self) -> None:
        """Validate selections and generate PivotTable."""
        if not self._parse_range_input() or self.r2 <= self.r1:
            QMessageBox.warning(
                self,
                safe_tr("数据透视表向导"),
                safe_tr(
                    "The PivotTable field name is not valid. To create a PivotTable report, you must use data that is organized as a list with labeled columns."
                ),
            )
            return

        row_col = self.combo_row.currentData()
        col_col = self.combo_col.currentData()
        data_col = self.combo_data.currentData()
        page_col = self.combo_page.currentData()
        fn_code = self.combo_fn.currentData() or "sum"

        if row_col is None or data_col is None:
            QMessageBox.warning(
                self,
                safe_tr("数据透视表向导"),
                safe_tr("请选择有效的行字段与数据字段。"),
            )
            return

        target_mode = "new" if self.radio_new_sheet.isChecked() else self.sheet_name
        active_sheet = self.workbook.active_sheet
        target_cell = (0, 0)
        if not self.radio_new_sheet.isChecked() and active_sheet:
            target_cell = (self.r2 + 2, self.c1)

        cfg = PivotConfig(
            source_sheet=self.sheet_name,
            source_range=(self.r1, self.c1, self.r2, self.c2),
            row_field_col=row_col,
            col_field_col=col_col,
            data_field_col=data_col,
            agg_func=fn_code,
            page_field_col=page_col,
            target_sheet=target_mode,
            target_cell=target_cell,
        )

        try:
            self.created_sheet, self.result_bbox = build_pivot_table(
                self.workbook, cfg
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(
                self,
                safe_tr("数据透视表生成失败"),
                f"{safe_tr('生成数据透视表时出错:')} {exc}",
            )
