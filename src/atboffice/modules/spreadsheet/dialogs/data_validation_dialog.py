"""Excel 2003 classic 3-tab Data Validation Dialog and Error Alert Dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.models.validation import (
    AlertStyle,
    DataValidation,
    ValidationOp,
    ValidationType,
)

if TYPE_CHECKING:
    pass


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("DataValidationDialog", text)


class DataValidationDialog(QDialog):
    """Excel 2003 classic 3-tab Data Validation Dialog."""

    def __init__(
        self,
        existing_dv: DataValidation | None = None,
        sqref: str = "A1",
        ranges: list[tuple[int, int, int, int]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sqref = sqref
        self.ranges = ranges or []

        self.setWindowTitle(safe_tr("Data Validation"))
        self.setMinimumWidth(440)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        self.tab_widget = QTabWidget(self)

        # -------------------------------------------------------------
        # Tab 1: Settings
        # -------------------------------------------------------------
        self.tab_settings = QWidget(self)
        s_layout = QVBoxLayout(self.tab_settings)

        form_allow = QFormLayout()
        self.combo_allow = QComboBox(self.tab_settings)
        self.combo_allow.addItem(safe_tr("Any value"), ValidationType.ANY.value)
        self.combo_allow.addItem(safe_tr("Whole number"), ValidationType.WHOLE.value)
        self.combo_allow.addItem(safe_tr("Decimal"), ValidationType.DECIMAL.value)
        self.combo_allow.addItem(safe_tr("List"), ValidationType.LIST.value)
        self.combo_allow.addItem(safe_tr("Date"), ValidationType.DATE.value)
        self.combo_allow.addItem(safe_tr("Time"), ValidationType.TIME.value)
        self.combo_allow.addItem(safe_tr("Text length"), ValidationType.TEXT_LENGTH.value)
        self.combo_allow.addItem(safe_tr("Custom"), ValidationType.CUSTOM.value)
        form_allow.addRow(safe_tr("Allow:"), self.combo_allow)

        self.check_ignore_blank = QCheckBox(safe_tr("Ignore blank"), self.tab_settings)
        self.check_ignore_blank.setChecked(True)
        form_allow.addRow("", self.check_ignore_blank)

        self.check_in_cell_dropdown = QCheckBox(safe_tr("In-cell dropdown"), self.tab_settings)
        self.check_in_cell_dropdown.setChecked(True)
        form_allow.addRow("", self.check_in_cell_dropdown)

        self.combo_op = QComboBox(self.tab_settings)
        self.combo_op.addItem(safe_tr("between"), ValidationOp.BETWEEN.value)
        self.combo_op.addItem(safe_tr("not between"), ValidationOp.NOT_BETWEEN.value)
        self.combo_op.addItem(safe_tr("equal to"), ValidationOp.EQUAL.value)
        self.combo_op.addItem(safe_tr("not equal to"), ValidationOp.NOT_EQUAL.value)
        self.combo_op.addItem(safe_tr("greater than"), ValidationOp.GREATER_THAN.value)
        self.combo_op.addItem(safe_tr("less than"), ValidationOp.LESS_THAN.value)
        self.combo_op.addItem(
            safe_tr("greater than or equal to"), ValidationOp.GREATER_THAN_OR_EQUAL.value
        )
        self.combo_op.addItem(
            safe_tr("less than or equal to"), ValidationOp.LESS_THAN_OR_EQUAL.value
        )
        self.lbl_data = QLabel(safe_tr("Data:"))
        form_allow.addRow(self.lbl_data, self.combo_op)

        self.edit_min = QLineEdit(self.tab_settings)
        self.lbl_min = QLabel(safe_tr("Minimum:"))
        form_allow.addRow(self.lbl_min, self.edit_min)

        self.edit_max = QLineEdit(self.tab_settings)
        self.lbl_max = QLabel(safe_tr("Maximum:"))
        form_allow.addRow(self.lbl_max, self.edit_max)

        s_layout.addLayout(form_allow)
        s_layout.addStretch()
        self.tab_widget.addTab(self.tab_settings, safe_tr("Settings"))

        # -------------------------------------------------------------
        # Tab 2: Input Message
        # -------------------------------------------------------------
        self.tab_input_msg = QWidget(self)
        im_layout = QVBoxLayout(self.tab_input_msg)

        self.check_show_input_msg = QCheckBox(
            safe_tr("Show input message when cell is selected"), self.tab_input_msg
        )
        im_layout.addWidget(self.check_show_input_msg)

        form_im = QFormLayout()
        self.edit_input_title = QLineEdit(self.tab_input_msg)
        form_im.addRow(safe_tr("Title:"), self.edit_input_title)

        self.edit_input_body = QTextEdit(self.tab_input_msg)
        self.edit_input_body.setMaximumHeight(90)
        form_im.addRow(safe_tr("Input message:"), self.edit_input_body)
        im_layout.addLayout(form_im)
        im_layout.addStretch()
        self.tab_widget.addTab(self.tab_input_msg, safe_tr("Input Message"))

        # -------------------------------------------------------------
        # Tab 3: Error Alert
        # -------------------------------------------------------------
        self.tab_error_alert = QWidget(self)
        ea_layout = QVBoxLayout(self.tab_error_alert)

        self.check_show_err_alert = QCheckBox(
            safe_tr("Show error alert after invalid data is entered"), self.tab_error_alert
        )
        self.check_show_err_alert.setChecked(True)
        ea_layout.addWidget(self.check_show_err_alert)

        form_ea = QFormLayout()
        self.combo_err_style = QComboBox(self.tab_error_alert)
        self.combo_err_style.addItem(safe_tr("Stop"), AlertStyle.STOP.value)
        self.combo_err_style.addItem(safe_tr("Warning"), AlertStyle.WARNING.value)
        self.combo_err_style.addItem(safe_tr("Information"), AlertStyle.INFORMATION.value)
        form_ea.addRow(safe_tr("Style:"), self.combo_err_style)

        self.edit_err_title = QLineEdit(self.tab_error_alert)
        form_ea.addRow(safe_tr("Title:"), self.edit_err_title)

        self.edit_err_body = QTextEdit(self.tab_error_alert)
        self.edit_err_body.setMaximumHeight(90)
        form_ea.addRow(safe_tr("Error message:"), self.edit_err_body)
        ea_layout.addLayout(form_ea)
        ea_layout.addStretch()
        self.tab_widget.addTab(self.tab_error_alert, safe_tr("Error Alert"))

        main_layout.addWidget(self.tab_widget)

        # Bottom Buttons
        bottom_layout = QHBoxLayout()
        self.btn_clear_all = QPushButton(safe_tr("Clear All"), self)
        self.btn_clear_all.clicked.connect(self._clear_all)
        bottom_layout.addWidget(self.btn_clear_all)
        bottom_layout.addStretch()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        bottom_layout.addWidget(self.button_box)
        main_layout.addLayout(bottom_layout)

        # Signals
        self.combo_allow.currentIndexChanged.connect(self._on_allow_changed)
        self.combo_op.currentIndexChanged.connect(self._on_op_changed)

        if existing_dv:
            self.load_data_validation(existing_dv)
        else:
            self._on_allow_changed()

    def _on_allow_changed(self) -> None:
        val_type = self.combo_allow.currentData()
        is_any = val_type == ValidationType.ANY.value
        is_list = val_type == ValidationType.LIST.value
        is_custom = val_type == ValidationType.CUSTOM.value

        self.check_ignore_blank.setEnabled(not is_any)
        self.check_in_cell_dropdown.setVisible(is_list)
        self.check_in_cell_dropdown.setEnabled(is_list)

        self.lbl_data.setVisible(not is_any and not is_list and not is_custom)
        self.combo_op.setVisible(not is_any and not is_list and not is_custom)

        if is_list:
            self.lbl_min.setText(safe_tr("Source:"))
            self.lbl_min.setVisible(True)
            self.edit_min.setVisible(True)
            self.lbl_max.setVisible(False)
            self.edit_max.setVisible(False)
        elif is_custom:
            self.lbl_min.setText(safe_tr("Formula:"))
            self.lbl_min.setVisible(True)
            self.edit_min.setVisible(True)
            self.lbl_max.setVisible(False)
            self.edit_max.setVisible(False)
        elif is_any:
            self.lbl_min.setVisible(False)
            self.edit_min.setVisible(False)
            self.lbl_max.setVisible(False)
            self.edit_max.setVisible(False)
        else:
            self.lbl_min.setText(safe_tr("Minimum:"))
            self.lbl_min.setVisible(True)
            self.edit_min.setVisible(True)
            self._on_op_changed()

    def _on_op_changed(self) -> None:
        val_type = self.combo_allow.currentData()
        if val_type in (
            ValidationType.ANY.value,
            ValidationType.LIST.value,
            ValidationType.CUSTOM.value,
        ):
            return
        op = self.combo_op.currentData()
        is_between = op in (ValidationOp.BETWEEN.value, ValidationOp.NOT_BETWEEN.value)
        self.lbl_max.setVisible(is_between)
        self.edit_max.setVisible(is_between)

    def _clear_all(self) -> None:
        self.combo_allow.setCurrentIndex(0)
        self.edit_min.clear()
        self.edit_max.clear()
        self.edit_input_title.clear()
        self.edit_input_body.clear()
        self.edit_err_title.clear()
        self.edit_err_body.clear()
        self.check_show_input_msg.setChecked(False)
        self.check_show_err_alert.setChecked(True)
        self.combo_err_style.setCurrentIndex(0)

    def get_data_validation(self) -> DataValidation:
        val_type = self.combo_allow.currentData()
        op = (
            self.combo_op.currentData()
            if val_type
            not in (
                ValidationType.ANY.value,
                ValidationType.LIST.value,
                ValidationType.CUSTOM.value,
            )
            else ValidationOp.BETWEEN.value
        )
        f1 = self.edit_min.text().strip() or None
        f2 = self.edit_max.text().strip() or None

        return DataValidation(
            type=val_type,
            operator=op,
            allow_blank=self.check_ignore_blank.isChecked(),
            show_dropdown=self.check_in_cell_dropdown.isChecked(),
            show_input_message=self.check_show_input_msg.isChecked(),
            input_title=self.edit_input_title.text().strip(),
            input_message=self.edit_input_body.toPlainText().strip(),
            show_error_alert=self.check_show_err_alert.isChecked(),
            error_style=self.combo_err_style.currentData(),
            error_title=self.edit_err_title.text().strip(),
            error_message=self.edit_err_body.toPlainText().strip(),
            formula1=f1,
            formula2=f2,
            sqref=self.sqref,
            ranges=self.ranges,
        )

    def load_data_validation(self, dv: DataValidation) -> None:
        idx = self.combo_allow.findData(dv.type)
        if idx >= 0:
            self.combo_allow.setCurrentIndex(idx)
        op_idx = self.combo_op.findData(dv.operator)
        if op_idx >= 0:
            self.combo_op.setCurrentIndex(op_idx)

        self.check_ignore_blank.setChecked(dv.allow_blank)
        self.check_in_cell_dropdown.setChecked(dv.show_dropdown)
        if dv.formula1:
            self.edit_min.setText(dv.formula1)
        if dv.formula2:
            self.edit_max.setText(dv.formula2)

        self.check_show_input_msg.setChecked(dv.show_input_message)
        self.edit_input_title.setText(dv.input_title)
        self.edit_input_body.setPlainText(dv.input_message)

        self.check_show_err_alert.setChecked(dv.show_error_alert)
        style_idx = self.combo_err_style.findData(dv.error_style)
        if style_idx >= 0:
            self.combo_err_style.setCurrentIndex(style_idx)
        self.edit_err_title.setText(dv.error_title)
        self.edit_err_body.setPlainText(dv.error_message)

        self._on_allow_changed()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("Data Validation"))
        self.tab_widget.setTabText(0, safe_tr("Settings"))
        self.tab_widget.setTabText(1, safe_tr("Input Message"))
        self.tab_widget.setTabText(2, safe_tr("Error Alert"))


class ValidationAlertDialog(QMessageBox):
    """Excel 2003 modal alert for data validation failures."""

    def __init__(
        self,
        parent: QWidget | None = None,
        style: str = AlertStyle.STOP.value,
        title: str = "",
        message: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title or safe_tr("Microsoft Excel"))
        self.setText(message or safe_tr("The value you entered is not valid."))

        if style == AlertStyle.WARNING.value:
            self.setIcon(QMessageBox.Icon.Warning)
            self.setStandardButtons(
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel
            )
            self.setDefaultButton(QMessageBox.StandardButton.No)
        elif style == AlertStyle.INFORMATION.value:
            self.setIcon(QMessageBox.Icon.Information)
            self.setStandardButtons(
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
            )
            self.setDefaultButton(QMessageBox.StandardButton.Ok)
        else:
            # STOP
            self.setIcon(QMessageBox.Icon.Critical)
            self.setStandardButtons(
                QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel
            )
            self.setDefaultButton(QMessageBox.StandardButton.Retry)
