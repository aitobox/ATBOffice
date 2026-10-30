"""Classic Insert Table Dialog for Quire Writer."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("InsertTableDialog", text)


class InsertTableDialog(QDialog):
    """Word 2003 classic Insert Table modal dialog."""

    def __init__(
        self,
        parent: QWidget | None = None,
        initial_cols: int = 5,
        initial_rows: int = 2,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("插入表格"))
        self.setModal(True)
        self.setMinimumWidth(320)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # 1. Table size group
        self.group_size = QGroupBox(self)
        grid_size = QGridLayout(self.group_size)
        grid_size.setSpacing(8)

        self.label_cols = QLabel(self.group_size)
        self.spin_cols = QSpinBox(self.group_size)
        self.spin_cols.setRange(1, 63)
        self.spin_cols.setValue(max(1, min(63, initial_cols)))

        self.label_rows = QLabel(self.group_size)
        self.spin_rows = QSpinBox(self.group_size)
        self.spin_rows.setRange(1, 32767)
        self.spin_rows.setValue(max(1, min(32767, initial_rows)))

        grid_size.addWidget(self.label_cols, 0, 0)
        grid_size.addWidget(self.spin_cols, 0, 1)
        grid_size.addWidget(self.label_rows, 1, 0)
        grid_size.addWidget(self.spin_rows, 1, 1)
        main_layout.addWidget(self.group_size)

        # 2. AutoFit behavior group
        self.group_autofit = QGroupBox(self)
        layout_autofit = QVBoxLayout(self.group_autofit)
        layout_autofit.setSpacing(6)

        self.btn_group_fit = QButtonGroup(self)

        # Fixed column width
        row_fixed = QHBoxLayout()
        self.radio_fixed = QRadioButton(self.group_autofit)
        self.radio_fixed.setChecked(True)
        self.spin_col_width = QDoubleSpinBox(self.group_autofit)
        self.spin_col_width.setRange(9.0, 1500.0)
        self.spin_col_width.setValue(72.0)
        self.spin_col_width.setSuffix(" pt")
        row_fixed.addWidget(self.radio_fixed)
        row_fixed.addWidget(self.spin_col_width)
        layout_autofit.addLayout(row_fixed)

        # Contents / Window
        self.radio_contents = QRadioButton(self.group_autofit)
        self.radio_window = QRadioButton(self.group_autofit)
        layout_autofit.addWidget(self.radio_contents)
        layout_autofit.addWidget(self.radio_window)

        self.btn_group_fit.addButton(self.radio_fixed, 0)
        self.btn_group_fit.addButton(self.radio_contents, 1)
        self.btn_group_fit.addButton(self.radio_window, 2)

        self.radio_fixed.toggled.connect(self._on_fit_mode_changed)

        main_layout.addWidget(self.group_autofit)

        # 3. Remember checkbox
        self.check_remember = QCheckBox(self)
        main_layout.addWidget(self.check_remember)

        # 4. Dialog button box
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.retranslate_ui()

    def _on_fit_mode_changed(self, checked: bool) -> None:
        self.spin_col_width.setEnabled(checked)

    def retranslate_ui(self) -> None:
        """Update all translatable strings dynamically."""
        self.setWindowTitle(safe_tr("插入表格"))
        self.group_size.setTitle(safe_tr("表格尺寸"))
        self.label_cols.setText(safe_tr("列数(&C):"))
        self.label_rows.setText(safe_tr("行数(&R):"))

        self.group_autofit.setTitle(safe_tr("“自动调整”操作"))
        self.radio_fixed.setText(safe_tr("固定列宽(&X):"))
        self.radio_contents.setText(safe_tr("根据内容调整表格(&F)"))
        self.radio_window.setText(safe_tr("根据窗口调整表格(&W)"))

        self.check_remember.setText(safe_tr("记住新表格的尺寸(&N)"))

        ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(safe_tr("确定"))
        cancel_btn = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(safe_tr("取消"))

    def get_dimensions(self) -> tuple[int, int, str, float | None]:
        """Return (cols, rows, fit_mode, col_width_pt)."""
        cols = self.spin_cols.value()
        rows = self.spin_rows.value()
        if self.radio_contents.isChecked():
            fit_mode = "contents"
            cw = None
        elif self.radio_window.isChecked():
            fit_mode = "window"
            cw = None
        else:
            fit_mode = "fixed"
            cw = float(self.spin_col_width.value())
        return cols, rows, fit_mode, cw
