"""Format floating object (shape, image, chart, textbox) dialog for Ledger."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.views.object_layer import AnchorType

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.views.object_layer import FloatingObject


class FormatObjectDialog(QDialog):
    """Excel 2003 classic Format AutoShape / Format Object dialog."""

    def __init__(
        self,
        obj: FloatingObject,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.obj = obj

        # Determine dialog title by object kind
        kind = getattr(obj, "kind", "shape")
        if kind == "chart":
            title = safe_tr("Format Chart Area")
        elif kind == "image":
            title = safe_tr("Format Picture")
        elif kind == "textbox":
            title = safe_tr("Format Text Box")
        else:
            title = safe_tr("Format AutoShape")
        self.setWindowTitle(title)
        self.resize(460, 380)

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget(self)

        # Tab 1: Colors & Lines
        self.tab_colors = QWidget(self)
        colors_layout = QVBoxLayout(self.tab_colors)

        # Fill Group
        self.grp_fill = QGroupBox(safe_tr("Fill"), self.tab_colors)
        form_fill = QFormLayout(self.grp_fill)
        self.lbl_fill_color = QLabel(safe_tr("&Color:"), self.grp_fill)
        self.btn_fill_color = QPushButton(self.grp_fill)
        self._current_fill_color = getattr(obj, "fill_color", "#4F81BD")
        self._update_color_button(self.btn_fill_color, self._current_fill_color)
        self.btn_fill_color.clicked.connect(self._choose_fill_color)
        form_fill.addRow(self.lbl_fill_color, self.btn_fill_color)

        self.lbl_transparency = QLabel(safe_tr("&Transparency:"), self.grp_fill)
        self.spin_transparency = QSpinBox(self.grp_fill)
        self.spin_transparency.setRange(0, 100)
        self.spin_transparency.setSuffix("%")
        fill_alpha = getattr(obj, "fill_alpha", 1.0)
        self.spin_transparency.setValue(int((1.0 - fill_alpha) * 100))
        form_fill.addRow(self.lbl_transparency, self.spin_transparency)
        colors_layout.addWidget(self.grp_fill)

        # Line Group
        self.grp_line = QGroupBox(safe_tr("Line"), self.tab_colors)
        form_line = QFormLayout(self.grp_line)
        self.lbl_line_color = QLabel(safe_tr("C&olor:"), self.grp_line)
        self.btn_line_color = QPushButton(self.grp_line)
        self._current_line_color = getattr(obj, "line_color", "#385D8A")
        self._update_color_button(self.btn_line_color, self._current_line_color)
        self.btn_line_color.clicked.connect(self._choose_line_color)
        form_line.addRow(self.lbl_line_color, self.btn_line_color)

        self.lbl_line_width = QLabel(safe_tr("&Weight:"), self.grp_line)
        self.spin_line_width = QDoubleSpinBox(self.grp_line)
        self.spin_line_width.setRange(0.25, 20.0)
        self.spin_line_width.setSingleStep(0.25)
        self.spin_line_width.setSuffix(" pt")
        self.spin_line_width.setValue(float(getattr(obj, "line_width", 1.0)))
        form_line.addRow(self.lbl_line_width, self.spin_line_width)
        colors_layout.addWidget(self.grp_line)
        colors_layout.addStretch()

        self.tab_widget.addTab(self.tab_colors, safe_tr("Colors and &Lines"))

        # Tab 2: Size
        self.tab_size = QWidget(self)
        size_layout = QVBoxLayout(self.tab_size)
        self.grp_size = QGroupBox(safe_tr("Size and rotate"), self.tab_size)
        form_size = QFormLayout(self.grp_size)

        rect = getattr(obj, "abs_rect", (0, 0, 120, 80))
        curr_w = rect[2] if len(rect) >= 3 else 120
        curr_h = rect[3] if len(rect) >= 4 else 80

        self.lbl_height = QLabel(safe_tr("&Height:"), self.grp_size)
        self.spin_height = QSpinBox(self.grp_size)
        self.spin_height.setRange(5, 5000)
        self.spin_height.setSuffix(" px")
        self.spin_height.setValue(curr_h)
        form_size.addRow(self.lbl_height, self.spin_height)

        self.lbl_width = QLabel(safe_tr("&Width:"), self.grp_size)
        self.spin_width = QSpinBox(self.grp_size)
        self.spin_width.setRange(5, 5000)
        self.spin_width.setSuffix(" px")
        self.spin_width.setValue(curr_w)
        form_size.addRow(self.lbl_width, self.spin_width)
        size_layout.addWidget(self.grp_size)
        size_layout.addStretch()

        self.tab_widget.addTab(self.tab_size, safe_tr("&Size"))

        # Tab 3: Properties
        self.tab_props = QWidget(self)
        props_layout = QVBoxLayout(self.tab_props)
        self.grp_pos = QGroupBox(safe_tr("Object positioning"), self.tab_props)
        pos_layout = QVBoxLayout(self.grp_pos)

        self.radio_two_cell = QRadioButton(
            safe_tr("&Move and size with cells"), self.grp_pos
        )
        self.radio_one_cell = QRadioButton(
            safe_tr("Move &but don't size with cells"), self.grp_pos
        )
        self.radio_absolute = QRadioButton(
            safe_tr("&Don't move or size with cells"), self.grp_pos
        )

        self.btn_group_pos = QButtonGroup(self.grp_pos)
        self.btn_group_pos.addButton(self.radio_two_cell, 0)
        self.btn_group_pos.addButton(self.radio_one_cell, 1)
        self.btn_group_pos.addButton(self.radio_absolute, 2)

        cur_anchor = getattr(obj, "anchor_type", AnchorType.TWO_CELL)
        if cur_anchor == AnchorType.ONE_CELL:
            self.radio_one_cell.setChecked(True)
        elif cur_anchor == AnchorType.ABSOLUTE:
            self.radio_absolute.setChecked(True)
        else:
            self.radio_two_cell.setChecked(True)

        pos_layout.addWidget(self.radio_two_cell)
        pos_layout.addWidget(self.radio_one_cell)
        pos_layout.addWidget(self.radio_absolute)
        props_layout.addWidget(self.grp_pos)

        form_alt = QFormLayout()
        self.lbl_alt = QLabel(safe_tr("Alt Te&xt:"), self.tab_props)
        self.edit_alt = QLineEdit(getattr(obj, "name", ""), self.tab_props)
        form_alt.addRow(self.lbl_alt, self.edit_alt)
        props_layout.addLayout(form_alt)
        props_layout.addStretch()

        self.tab_widget.addTab(self.tab_props, safe_tr("&Properties"))
        main_layout.addWidget(self.tab_widget)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self._apply_and_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def _update_color_button(self, btn: QPushButton, color_hex: str) -> None:
        btn.setStyleSheet(
            f"background-color: {color_hex}; border: 1px solid #777; min-height: 22px;"
        )
        btn.setText(color_hex)

    def _choose_fill_color(self) -> None:
        initial = QColor(self._current_fill_color)
        col = QColorDialog.getColor(initial, self, safe_tr("&Color:"))
        if col.isValid():
            self._current_fill_color = col.name()
            self._update_color_button(self.btn_fill_color, self._current_fill_color)

    def _choose_line_color(self) -> None:
        initial = QColor(self._current_line_color)
        col = QColorDialog.getColor(initial, self, safe_tr("C&olor:"))
        if col.isValid():
            self._current_line_color = col.name()
            self._update_color_button(self.btn_line_color, self._current_line_color)

    def _apply_and_accept(self) -> None:
        """Apply user modifications to the FloatingObject and accept dialog."""
        self.obj.fill_color = self._current_fill_color
        self.obj.fill_alpha = round(1.0 - (self.spin_transparency.value() / 100.0), 2)
        self.obj.line_color = self._current_line_color
        self.obj.line_width = self.spin_line_width.value()

        rect = getattr(self.obj, "abs_rect", (0, 0, 120, 80))
        rx = rect[0] if len(rect) >= 1 else 0
        ry = rect[1] if len(rect) >= 2 else 0
        new_w = self.spin_width.value()
        new_h = self.spin_height.value()
        self.obj.abs_rect = (rx, ry, new_w, new_h)

        if self.radio_one_cell.isChecked():
            self.obj.anchor_type = AnchorType.ONE_CELL
        elif self.radio_absolute.isChecked():
            self.obj.anchor_type = AnchorType.ABSOLUTE
        else:
            self.obj.anchor_type = AnchorType.TWO_CELL

        name = self.edit_alt.text().strip()
        if name:
            self.obj.name = name

        self.accept()

    def retranslate_ui(self) -> None:
        """Update localized UI strings."""
        kind = getattr(self.obj, "kind", "shape")
        if kind == "chart":
            title = safe_tr("Format Chart Area")
        elif kind == "image":
            title = safe_tr("Format Picture")
        elif kind == "textbox":
            title = safe_tr("Format Text Box")
        else:
            title = safe_tr("Format AutoShape")
        self.setWindowTitle(title)

        self.tab_widget.setTabText(0, safe_tr("Colors and &Lines"))
        self.tab_widget.setTabText(1, safe_tr("&Size"))
        self.tab_widget.setTabText(2, safe_tr("&Properties"))

        self.grp_fill.setTitle(safe_tr("Fill"))
        self.lbl_fill_color.setText(safe_tr("&Color:"))
        self.lbl_transparency.setText(safe_tr("&Transparency:"))

        self.grp_line.setTitle(safe_tr("Line"))
        self.lbl_line_color.setText(safe_tr("C&olor:"))
        self.lbl_line_width.setText(safe_tr("&Weight:"))

        self.grp_size.setTitle(safe_tr("Size and rotate"))
        self.lbl_height.setText(safe_tr("&Height:"))
        self.lbl_width.setText(safe_tr("&Width:"))

        self.grp_pos.setTitle(safe_tr("Object positioning"))
        self.radio_two_cell.setText(safe_tr("&Move and size with cells"))
        self.radio_one_cell.setText(safe_tr("Move &but don't size with cells"))
        self.radio_absolute.setText(safe_tr("&Don't move or size with cells"))
        self.lbl_alt.setText(safe_tr("Alt Te&xt:"))

        ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(safe_tr("OK"))
        cancel_btn = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(safe_tr("Cancel"))
