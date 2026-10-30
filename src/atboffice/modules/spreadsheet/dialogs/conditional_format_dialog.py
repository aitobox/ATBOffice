"""Excel 2003 classic Conditional Formatting Dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.models.conditional_format import (
    CFOp,
    CFRule,
    CFRuleType,
    ConditionalFormat,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("ConditionalFormatDialog", text)


class ConditionRow(QGroupBox):
    """Single condition rule row in classic Excel 2003 style."""

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self.bg_color: str | None = None
        self.fg_color: str | None = None
        self.bold: bool = False
        self.italic: bool = False

        self.setTitle(safe_tr("Condition {0}").format(index + 1))
        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        self.combo_type = QComboBox(self)
        self.combo_type.addItem(safe_tr("Cell Value Is"), CFRuleType.CELL_IS.value)
        self.combo_type.addItem(safe_tr("Formula Is"), CFRuleType.EXPRESSION.value)

        self.combo_op = QComboBox(self)
        self.combo_op.addItem(safe_tr("between"), CFOp.BETWEEN.value)
        self.combo_op.addItem(safe_tr("not between"), CFOp.NOT_BETWEEN.value)
        self.combo_op.addItem(safe_tr("equal to"), CFOp.EQUAL.value)
        self.combo_op.addItem(safe_tr("not equal to"), CFOp.NOT_EQUAL.value)
        self.combo_op.addItem(safe_tr("greater than"), CFOp.GREATER_THAN.value)
        self.combo_op.addItem(safe_tr("less than"), CFOp.LESS_THAN.value)
        self.combo_op.addItem(safe_tr("greater than or equal to"), CFOp.GREATER_THAN_OR_EQUAL.value)
        self.combo_op.addItem(safe_tr("less than or equal to"), CFOp.LESS_THAN_OR_EQUAL.value)

        self.edit_val1 = QLineEdit(self)
        self.lbl_and = QLabel(safe_tr("and"), self)
        self.edit_val2 = QLineEdit(self)

        top_layout.addWidget(self.combo_type)
        top_layout.addWidget(self.combo_op)
        top_layout.addWidget(self.edit_val1)
        top_layout.addWidget(self.lbl_and)
        top_layout.addWidget(self.edit_val2)
        layout.addLayout(top_layout)

        bottom_layout = QHBoxLayout()
        self.preview_label = QLabel(safe_tr("Preview of format to use:"), self)
        self.preview_box = QLabel(safe_tr("AaBbCcYyZz"), self)
        self.preview_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_box.setFixedSize(140, 26)
        self._update_preview()

        self.btn_format = QPushButton(safe_tr("Format..."), self)
        self.btn_format.clicked.connect(self._on_format_clicked)

        bottom_layout.addWidget(self.preview_label)
        bottom_layout.addWidget(self.preview_box)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_format)
        layout.addLayout(bottom_layout)

        self.combo_type.currentIndexChanged.connect(self._on_type_changed)
        self.combo_op.currentIndexChanged.connect(self._on_op_changed)
        self._on_type_changed()

    def _on_type_changed(self) -> None:
        is_cell_is = self.combo_type.currentData() == CFRuleType.CELL_IS.value
        self.combo_op.setVisible(is_cell_is)
        self._on_op_changed()

    def _on_op_changed(self) -> None:
        is_cell_is = self.combo_type.currentData() == CFRuleType.CELL_IS.value
        op = self.combo_op.currentData()
        is_between = is_cell_is and op in (CFOp.BETWEEN.value, CFOp.NOT_BETWEEN.value)
        self.lbl_and.setVisible(is_between)
        self.edit_val2.setVisible(is_between)

    def _on_format_clicked(self) -> None:
        col = QColorDialog.getColor(
            QColor(self.bg_color or "#FFC7CE"),
            self,
            safe_tr("Select Background Fill Color"),
        )
        if col.isValid():
            self.bg_color = col.name().upper()
            self._update_preview()

    def _update_preview(self) -> None:
        bg = self.bg_color or "#FFFFFF"
        fg = self.fg_color or "#000000"
        style = (
            f"border: 1px solid #7F9DB9; background: {bg}; color: {fg}; "
            f"font-weight: {'bold' if self.bold else 'normal'}; "
            f"font-style: {'italic' if self.italic else 'normal'};"
        )
        self.preview_box.setStyleSheet(style)

    def to_rule(self, priority: int = 1) -> CFRule:
        rtype = self.combo_type.currentData()
        op = self.combo_op.currentData() if rtype == CFRuleType.CELL_IS.value else None
        f1 = self.edit_val1.text().strip()
        f2 = self.edit_val2.text().strip()
        formulas = [f1] if f1 else []
        if op in (CFOp.BETWEEN.value, CFOp.NOT_BETWEEN.value) and f2:
            formulas.append(f2)

        return CFRule(
            type=rtype,
            operator=op,
            formula=formulas,
            priority=priority,
            bg_color=self.bg_color,
            fg_color=self.fg_color,
            bold=self.bold,
            italic=self.italic,
        )

    def load_rule(self, rule: CFRule) -> None:
        idx = self.combo_type.findData(rule.type)
        if idx >= 0:
            self.combo_type.setCurrentIndex(idx)
        if rule.operator:
            op_idx = self.combo_op.findData(rule.operator)
            if op_idx >= 0:
                self.combo_op.setCurrentIndex(op_idx)
        if len(rule.formula) > 0:
            self.edit_val1.setText(rule.formula[0])
        if len(rule.formula) > 1:
            self.edit_val2.setText(rule.formula[1])
        self.bg_color = rule.bg_color
        self.fg_color = rule.fg_color
        self.bold = bool(rule.bold)
        self.italic = bool(rule.italic)
        self._update_preview()
        self._on_type_changed()


class ConditionalFormatDialog(QDialog):
    """Excel 2003 classic 3-condition Conditional Formatting dialog."""

    def __init__(
        self,
        existing_cf: ConditionalFormat | None = None,
        sqref: str = "A1",
        ranges: list[tuple[int, int, int, int]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sqref = sqref
        self.ranges = ranges or []
        self.rows: list[ConditionRow] = []

        self.setWindowTitle(safe_tr("Conditional Formatting"))
        self.setMinimumWidth(520)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(10)

        # Condition rows container
        self.rows_layout = QVBoxLayout()
        self.main_layout.addLayout(self.rows_layout)

        # Action buttons
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton(safe_tr("Add >>"), self)
        self.btn_add.clicked.connect(self._add_row)
        self.btn_delete = QPushButton(safe_tr("Delete..."), self)
        self.btn_delete.clicked.connect(self._delete_last_row)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        btn_layout.addWidget(self.button_box)

        self.main_layout.addLayout(btn_layout)

        if existing_cf and existing_cf.rules:
            for rule in existing_cf.rules[:3]:
                row = self._add_row()
                row.load_rule(rule)
        else:
            self._add_row()

    def _add_row(self) -> ConditionRow:
        if len(self.rows) >= 3:
            return self.rows[-1]
        row = ConditionRow(len(self.rows), self)
        self.rows.append(row)
        self.rows_layout.addWidget(row)
        self.btn_add.setEnabled(len(self.rows) < 3)
        self.btn_delete.setEnabled(len(self.rows) > 1)
        return row

    def _delete_last_row(self) -> None:
        if len(self.rows) <= 1:
            return
        row = self.rows.pop()
        self.rows_layout.removeWidget(row)
        row.deleteLater()
        self.btn_add.setEnabled(len(self.rows) < 3)
        self.btn_delete.setEnabled(len(self.rows) > 1)

    def get_conditional_format(self) -> ConditionalFormat:
        rules = [row.to_rule(priority=idx + 1) for idx, row in enumerate(self.rows)]
        return ConditionalFormat(
            sqref=self.sqref,
            ranges=self.ranges,
            rules=rules,
        )

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("Conditional Formatting"))
        self.btn_add.setText(safe_tr("Add >>"))
        self.btn_delete.setText(safe_tr("Delete..."))
