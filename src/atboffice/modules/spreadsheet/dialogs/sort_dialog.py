"""Excel 2003 classic 3-key Sort Dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.calc.references import col_name

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("SortDialog", text)


class SortDialog(QDialog):
    """Excel 2003 classic multi-column sort dialog."""

    def __init__(
        self,
        model: SheetDataModel,
        r1: int,
        c1: int,
        r2: int,
        c2: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.r1 = r1
        self.c1 = c1
        self.r2 = r2
        self.c2 = c2

        self.setWindowTitle(safe_tr("Sort"))
        self.setMinimumWidth(380)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # 1. Primary Sort Key ("Sort by")
        self.group_primary = QGroupBox(self)
        p_layout = QHBoxLayout(self.group_primary)
        self.combo_primary = QComboBox(self.group_primary)
        p_layout.addWidget(self.combo_primary, stretch=2)

        p_radio_layout = QVBoxLayout()
        self.p_radio_asc = QRadioButton(self.group_primary)
        self.p_radio_desc = QRadioButton(self.group_primary)
        self.p_radio_asc.setChecked(True)
        p_btn_group = QButtonGroup(self.group_primary)
        p_btn_group.addButton(self.p_radio_asc)
        p_btn_group.addButton(self.p_radio_desc)
        p_radio_layout.addWidget(self.p_radio_asc)
        p_radio_layout.addWidget(self.p_radio_desc)
        p_layout.addLayout(p_radio_layout, stretch=1)
        main_layout.addWidget(self.group_primary)

        # 2. Secondary Sort Key ("Then by")
        self.group_sec = QGroupBox(self)
        sec_layout = QHBoxLayout(self.group_sec)
        self.combo_sec = QComboBox(self.group_sec)
        sec_layout.addWidget(self.combo_sec, stretch=2)

        sec_radio_layout = QVBoxLayout()
        self.sec_radio_asc = QRadioButton(self.group_sec)
        self.sec_radio_desc = QRadioButton(self.group_sec)
        self.sec_radio_asc.setChecked(True)
        sec_btn_group = QButtonGroup(self.group_sec)
        sec_btn_group.addButton(self.sec_radio_asc)
        sec_btn_group.addButton(self.sec_radio_desc)
        sec_radio_layout.addWidget(self.sec_radio_asc)
        sec_radio_layout.addWidget(self.sec_radio_desc)
        sec_layout.addLayout(sec_radio_layout, stretch=1)
        main_layout.addWidget(self.group_sec)

        # 3. Third Sort Key ("Then by")
        self.group_third = QGroupBox(self)
        third_layout = QHBoxLayout(self.group_third)
        self.combo_third = QComboBox(self.group_third)
        third_layout.addWidget(self.combo_third, stretch=2)

        third_radio_layout = QVBoxLayout()
        self.third_radio_asc = QRadioButton(self.group_third)
        self.third_radio_desc = QRadioButton(self.group_third)
        self.third_radio_asc.setChecked(True)
        third_btn_group = QButtonGroup(self.group_third)
        third_btn_group.addButton(self.third_radio_asc)
        third_btn_group.addButton(self.third_radio_desc)
        third_radio_layout.addWidget(self.third_radio_asc)
        third_radio_layout.addWidget(self.third_radio_desc)
        third_layout.addLayout(third_radio_layout, stretch=1)
        main_layout.addWidget(self.group_third)

        # 4. Data Range Header option
        self.group_header = QGroupBox(self)
        h_layout = QHBoxLayout(self.group_header)
        self.radio_has_header = QRadioButton(self.group_header)
        self.radio_no_header = QRadioButton(self.group_header)
        self.radio_has_header.setChecked(True)
        header_group = QButtonGroup(self.group_header)
        header_group.addButton(self.radio_has_header)
        header_group.addButton(self.radio_no_header)
        h_layout.addWidget(self.radio_has_header)
        h_layout.addWidget(self.radio_no_header)
        main_layout.addWidget(self.group_header)

        # 5. Options (Case sensitive)
        self.check_case_sensitive = QCheckBox(self)
        main_layout.addWidget(self.check_case_sensitive)

        # 6. Dialog buttons (OK / Cancel)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # Connect signals
        self.radio_has_header.toggled.connect(self._update_column_combos)

        self._populate_column_combos()
        self.retranslate_ui()

    def has_header(self) -> bool:
        """Return True if 'Header row' is checked."""
        return self.radio_has_header.isChecked()

    def is_case_sensitive(self) -> bool:
        """Return True if 'Case sensitive' is checked."""
        return self.check_case_sensitive.isChecked()

    def get_sort_keys(self) -> list[tuple[int, bool]]:
        """Return list of (col_index, desc_bool) for active sort keys."""
        keys: list[tuple[int, bool]] = []

        # Primary key
        p_col = self.combo_primary.currentData()
        if p_col is not None:
            keys.append((int(p_col), self.p_radio_desc.isChecked()))

        # Secondary key
        s_col = self.combo_sec.currentData()
        if s_col is not None:
            keys.append((int(s_col), self.sec_radio_desc.isChecked()))

        # Third key
        t_col = self.combo_third.currentData()
        if t_col is not None:
            keys.append((int(t_col), self.third_radio_desc.isChecked()))

        return keys

    def _update_column_combos(self) -> None:
        """Refresh column combo labels when header row option changes."""
        # Preserve currently selected column indices
        p_sel = self.combo_primary.currentData()
        s_sel = self.combo_sec.currentData()
        t_sel = self.combo_third.currentData()

        self._populate_column_combos()

        if p_sel is not None:
            idx = self.combo_primary.findData(p_sel)
            if idx >= 0:
                self.combo_primary.setCurrentIndex(idx)

        if s_sel is not None:
            idx = self.combo_sec.findData(s_sel)
            if idx >= 0:
                self.combo_sec.setCurrentIndex(idx)

        if t_sel is not None:
            idx = self.combo_third.findData(t_sel)
            if idx >= 0:
                self.combo_third.setCurrentIndex(idx)

    def _populate_column_combos(self) -> None:
        """Populate column choices based on has_header."""
        self.combo_primary.clear()
        self.combo_sec.clear()
        self.combo_third.clear()

        # Secondary & third keys can be (none)
        none_label = safe_tr("(none)")
        self.combo_sec.addItem(none_label, None)
        self.combo_third.addItem(none_label, None)

        use_headers = self.has_header()

        for c in range(self.c1, self.c2 + 1):
            if use_headers:
                txt = self.model.get_formatted_text(self.r1, c)
                label = txt if txt.strip() else safe_tr("Column {0}").format(col_name(c))
            else:
                label = safe_tr("Column {0}").format(col_name(c))

            self.combo_primary.addItem(label, c)
            self.combo_sec.addItem(label, c)
            self.combo_third.addItem(label, c)

    def retranslate_ui(self) -> None:
        """Update localized strings."""
        self.setWindowTitle(safe_tr("Sort"))
        self.group_primary.setTitle(safe_tr("Sort by"))
        self.group_sec.setTitle(safe_tr("Then by"))
        self.group_third.setTitle(safe_tr("Then by"))

        self.p_radio_asc.setText(safe_tr("&Ascending"))
        self.p_radio_desc.setText(safe_tr("&Descending"))
        self.sec_radio_asc.setText(safe_tr("A&scending"))
        self.sec_radio_desc.setText(safe_tr("D&escending"))
        self.third_radio_asc.setText(safe_tr("Ascend&ing"))
        self.third_radio_desc.setText(safe_tr("Descend&ing"))

        self.group_header.setTitle(safe_tr("My data range has"))
        self.radio_has_header.setText(safe_tr("&Header row"))
        self.radio_no_header.setText(safe_tr("&No header row"))

        self.check_case_sensitive.setText(safe_tr("&Case sensitive"))
