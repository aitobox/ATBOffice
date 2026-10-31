"""Excel 2003 classic Custom AutoFilter dialog (自定义自动筛选方式)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    pass


def safe_tr(text: str) -> str:
    """Translate UI text for CustomFilterDialog."""
    return QCoreApplication.translate("CustomFilterDialog", text)


class CustomFilterDialog(QDialog):
    """Excel 2003 classic Custom AutoFilter dialog."""

    OPERATORS: list[tuple[str, str]] = [
        ("equal", "equals"),
        ("notEqual", "does not equal"),
        ("greaterThan", "is greater than"),
        ("greaterThanOrEqual", "is greater than or equal to"),
        ("lessThan", "is less than"),
        ("lessThanOrEqual", "is less than or equal to"),
        ("begins", "begins with"),
        ("notBegins", "does not begin with"),
        ("ends", "ends with"),
        ("notEnds", "does not end with"),
        ("contains", "contains"),
        ("notContains", "does not contain"),
    ]

    OPERATOR_I18N: dict[str, str] = {
        "equals": "等于",
        "does not equal": "不等于",
        "is greater than": "大于",
        "is greater than or equal to": "大于或等于",
        "is less than": "小于",
        "is less than or equal to": "小于或等于",
        "begins with": "开头是",
        "does not begin with": "开头不是",
        "ends with": "结尾是",
        "does not end with": "结尾不是",
        "contains": "包含",
        "does not contain": "不包含",
    }

    def __init__(
        self,
        column_header: str,
        unique_values: list[str],
        initial_conditions: list[tuple[str, str]] | None = None,
        initial_and: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.column_header = column_header
        self.unique_values = unique_values
        self.initial_conditions = initial_conditions or []
        self.initial_and = initial_and

        self.setWindowTitle(safe_tr("Custom AutoFilter"))
        self.setMinimumWidth(450)

        self._setup_ui()
        self._populate_initial_data()
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header prompt
        self.label_title = QLabel(self)
        layout.addWidget(self.label_title)

        self.label_col = QLabel(f"<b>{self.column_header}</b>", self)
        layout.addWidget(self.label_col)

        # Condition 1
        cond1_layout = QHBoxLayout()
        cond1_layout.setSpacing(8)
        self.op1 = QComboBox(self)
        self.val1 = QComboBox(self)
        self.val1.setEditable(True)
        cond1_layout.addWidget(self.op1, stretch=1)
        cond1_layout.addWidget(self.val1, stretch=1)
        layout.addLayout(cond1_layout)

        # And / Or radio buttons
        radio_layout = QHBoxLayout()
        radio_layout.setContentsMargins(40, 4, 0, 4)
        radio_layout.setSpacing(16)
        self.radio_and = QRadioButton(self)
        self.radio_or = QRadioButton(self)
        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.radio_and)
        self.btn_group.addButton(self.radio_or)
        radio_layout.addWidget(self.radio_and)
        radio_layout.addWidget(self.radio_or)
        radio_layout.addStretch()
        layout.addLayout(radio_layout)

        # Condition 2
        cond2_layout = QHBoxLayout()
        cond2_layout.setSpacing(8)
        self.op2 = QComboBox(self)
        self.val2 = QComboBox(self)
        self.val2.setEditable(True)
        cond2_layout.addWidget(self.op2, stretch=1)
        cond2_layout.addWidget(self.val2, stretch=1)
        layout.addLayout(cond2_layout)

        # Wildcard Hint label
        self.label_hint = QLabel(self)
        self.label_hint.setStyleSheet("color: #555; font-size: 11px; margin-top: 6px;")
        layout.addWidget(self.label_hint)

        # OK / Cancel buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _populate_initial_data(self) -> None:
        # Populate candidate values
        top_values = self.unique_values[:1000]
        self.val1.addItems(top_values)
        self.val2.addItems(top_values)

        # Populate operators
        self._reload_operators()

        # Restore initial conditions if provided
        if self.initial_conditions:
            cond1 = self.initial_conditions[0]
            idx1 = self.op1.findData(cond1[0])
            if idx1 >= 0:
                self.op1.setCurrentIndex(idx1)
            self.val1.setEditText(str(cond1[1]))

            if len(self.initial_conditions) > 1:
                cond2 = self.initial_conditions[1]
                idx2 = self.op2.findData(cond2[0])
                if idx2 >= 0:
                    self.op2.setCurrentIndex(idx2)
                self.val2.setEditText(str(cond2[1]))
            else:
                self.op2.setCurrentIndex(0)
                self.val2.setEditText("")
        else:
            self.op1.setCurrentIndex(0)
            self.val1.setEditText("")
            self.op2.setCurrentIndex(0)
            self.val2.setEditText("")

        if self.initial_and:
            self.radio_and.setChecked(True)
        else:
            self.radio_or.setChecked(True)

    def _reload_operators(self) -> None:
        cur_code1 = self.op1.currentData()
        cur_code2 = self.op2.currentData()

        self.op1.clear()
        for code, label in self.OPERATORS:
            translated = safe_tr(label)
            if translated == label:
                translated = self.OPERATOR_I18N.get(label, label)
            self.op1.addItem(translated, code)

        self.op2.clear()
        self.op2.addItem("", "")
        for code, label in self.OPERATORS:
            translated = safe_tr(label)
            if translated == label:
                translated = self.OPERATOR_I18N.get(label, label)
            self.op2.addItem(translated, code)

        if cur_code1:
            idx = self.op1.findData(cur_code1)
            if idx >= 0:
                self.op1.setCurrentIndex(idx)
        if cur_code2:
            idx = self.op2.findData(cur_code2)
            if idx >= 0:
                self.op2.setCurrentIndex(idx)

    def retranslate_ui(self) -> None:
        """Retranslate all UI labels and options."""
        self.setWindowTitle(safe_tr("Custom AutoFilter"))
        title_text = safe_tr("Show rows where:")
        if title_text == "Show rows where:":
            title_text = "显示行:"
        self.label_title.setText(title_text)

        and_text = safe_tr("&And")
        if and_text == "&And":
            and_text = "与(&A)"
        self.radio_and.setText(and_text)

        or_text = safe_tr("&Or")
        if or_text == "&Or":
            or_text = "或(&O)"
        self.radio_or.setText(or_text)

        hint_text = safe_tr(
            "Use ? to represent any single character\nUse * to represent any series of characters"
        )
        if "Use ?" in hint_text:
            hint_text = "用 ? 代表单个字符\n用 * 代表任意多个字符"
        self.label_hint.setText(hint_text)

        self._reload_operators()

    def get_custom_criteria(self) -> tuple[list[tuple[str, str]], bool]:
        """Return (criteria_list, is_and). Criteria format: [(op, val_pattern), ...]."""
        criteria: list[tuple[str, str]] = []

        code1 = self.op1.currentData()
        v1 = self.val1.currentText().strip()
        if code1 and v1:
            criteria.append((str(code1), v1))

        code2 = self.op2.currentData()
        v2 = self.val2.currentText().strip()
        if code2 and v2:
            criteria.append((str(code2), v2))

        is_and = self.radio_and.isChecked()
        return criteria, is_and
