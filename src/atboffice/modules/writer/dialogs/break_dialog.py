"""Break Dialog for Quire Writer.

Allows inserting page, column, text wrapping breaks, and various section breaks.
Aligned with classic Word / VibeOffice Break dialog.
"""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("BreakDialog", text)


class BreakDialog(QDialog):
    """Classic Break and Section Break insertion dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("分隔符"))
        self.resize(280, 260)

        main_layout = QVBoxLayout(self)

        # 1. Break types group
        self.grp_break_types = QGroupBox(safe_tr("分隔符类型"), self)
        l_breaks = QVBoxLayout(self.grp_break_types)

        self.radio_page = QRadioButton(safe_tr("分页符(&P)"), self.grp_break_types)
        self.radio_column = QRadioButton(safe_tr("分栏符(&C)"), self.grp_break_types)
        self.radio_wrap = QRadioButton(safe_tr("文字环绕符(&W)"), self.grp_break_types)
        self.radio_page.setChecked(True)

        l_breaks.addWidget(self.radio_page)
        l_breaks.addWidget(self.radio_column)
        l_breaks.addWidget(self.radio_wrap)
        main_layout.addWidget(self.grp_break_types)

        # 2. Section break types group
        self.grp_section_types = QGroupBox(safe_tr("分节符类型"), self)
        l_sections = QVBoxLayout(self.grp_section_types)

        self.radio_next_page = QRadioButton(safe_tr("下一页(&N)"), self.grp_section_types)
        self.radio_continuous = QRadioButton(safe_tr("连续(&T)"), self.grp_section_types)
        self.radio_even_page = QRadioButton(safe_tr("偶数页(&E)"), self.grp_section_types)
        self.radio_odd_page = QRadioButton(safe_tr("奇数页(&O)"), self.grp_section_types)

        l_sections.addWidget(self.radio_next_page)
        l_sections.addWidget(self.radio_continuous)
        l_sections.addWidget(self.radio_even_page)
        l_sections.addWidget(self.radio_odd_page)
        main_layout.addWidget(self.grp_section_types)

        # Button group to ensure single selection across both groups
        self.button_group = QButtonGroup(self)
        self.button_group.addButton(self.radio_page, 0)
        self.button_group.addButton(self.radio_column, 1)
        self.button_group.addButton(self.radio_wrap, 2)
        self.button_group.addButton(self.radio_next_page, 3)
        self.button_group.addButton(self.radio_continuous, 4)
        self.button_group.addButton(self.radio_even_page, 5)
        self.button_group.addButton(self.radio_odd_page, 6)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def get_break_type(self) -> tuple[str, str]:
        """Return (category, break_type).

        Categories: 'break' or 'section'
        Break types:
          - 'page', 'column', 'wrap'
          - 'nextPage', 'continuous', 'evenPage', 'oddPage'
        """
        if self.radio_page.isChecked():
            return ("break", "page")
        if self.radio_column.isChecked():
            return ("break", "column")
        if self.radio_wrap.isChecked():
            return ("break", "wrap")
        if self.radio_next_page.isChecked():
            return ("section", "nextPage")
        if self.radio_continuous.isChecked():
            return ("section", "continuous")
        if self.radio_even_page.isChecked():
            return ("section", "evenPage")
        if self.radio_odd_page.isChecked():
            return ("section", "oddPage")
        return ("break", "page")

    def retranslate_ui(self) -> None:
        """Update texts upon language change."""
        self.setWindowTitle(safe_tr("分隔符"))
        self.grp_break_types.setTitle(safe_tr("分隔符类型"))
        self.radio_page.setText(safe_tr("分页符(&P)"))
        self.radio_column.setText(safe_tr("分栏符(&C)"))
        self.radio_wrap.setText(safe_tr("文字环绕符(&W)"))

        self.grp_section_types.setTitle(safe_tr("分节符类型"))
        self.radio_next_page.setText(safe_tr("下一页(&N)"))
        self.radio_continuous.setText(safe_tr("连续(&T)"))
        self.radio_even_page.setText(safe_tr("偶数页(&E)"))
        self.radio_odd_page.setText(safe_tr("奇数页(&O)"))
