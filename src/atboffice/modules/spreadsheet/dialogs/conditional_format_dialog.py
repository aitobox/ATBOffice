"""Excel 2003 classic Conditional Formatting Dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
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

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.models.conditional_format import (
    CFVO,
    CFOp,
    CFRule,
    CFRuleType,
    ColorScaleRule,
    ConditionalFormat,
    DataBarRule,
    IconSetRule,
)

# Rule kinds offered by the dialog (combo userData). Colour scales share one
# CFRuleType but differ in stop count.
KIND_CELL_IS = CFRuleType.CELL_IS.value
KIND_FORMULA = CFRuleType.EXPRESSION.value
KIND_SCALE2 = "colorScale2"
KIND_SCALE3 = "colorScale3"
KIND_DATA_BAR = CFRuleType.DATA_BAR.value
KIND_ICON_SET = CFRuleType.ICON_SET.value

ICON_SET_CHOICES = [
    ("3Arrows", "3 Arrows (Colored)"),
    ("3ArrowsGray", "3 Arrows (Gray)"),
    ("3Flags", "3 Flags"),
    ("3TrafficLights1", "3 Traffic Lights"),
    ("3Signs", "3 Signs"),
    ("3Symbols", "3 Symbols (Circled)"),
    ("4Arrows", "4 Arrows (Colored)"),
    ("4Rating", "4 Ratings"),
    ("4TrafficLights", "4 Traffic Lights"),
    ("5Arrows", "5 Arrows (Colored)"),
    ("5Rating", "5 Ratings"),
    ("5Quarters", "5 Quarters"),
]

if TYPE_CHECKING:
    pass


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
        self.combo_type.addItem(safe_tr("Cell Value Is"), KIND_CELL_IS)
        self.combo_type.addItem(safe_tr("Formula Is"), KIND_FORMULA)
        self.combo_type.addItem(safe_tr("2-Color Scale"), KIND_SCALE2)
        self.combo_type.addItem(safe_tr("3-Color Scale"), KIND_SCALE3)
        self.combo_type.addItem(safe_tr("Data Bar"), KIND_DATA_BAR)
        self.combo_type.addItem(safe_tr("Icon Set"), KIND_ICON_SET)

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

        # Colour scale / data bar / icon set settings
        self.scale_colors: list[str] = ["#F8696B", "#FFEB84", "#63BE7B"]
        self.bar_color: str = "#638EC6"
        visual_layout = QHBoxLayout()
        self.lbl_colors = QLabel(safe_tr("Colors:"), self)
        self.btn_colors: list[QPushButton] = []
        for idx in range(3):
            btn = QPushButton(self)
            btn.setFixedSize(48, 22)
            btn.clicked.connect(lambda _=False, i=idx: self._pick_scale_color(i))
            self.btn_colors.append(btn)
        self.combo_icons = QComboBox(self)
        for set_id, label in ICON_SET_CHOICES:
            self.combo_icons.addItem(safe_tr(label), set_id)
        self.chk_reverse = QCheckBox(safe_tr("Reverse icon order"), self)
        visual_layout.addWidget(self.lbl_colors)
        for btn in self.btn_colors:
            visual_layout.addWidget(btn)
        visual_layout.addWidget(self.combo_icons)
        visual_layout.addWidget(self.chk_reverse)
        visual_layout.addStretch()
        layout.addLayout(visual_layout)
        self._update_color_buttons()

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
        kind = self.combo_type.currentData()
        is_cell_is = kind == KIND_CELL_IS
        classic = kind in (KIND_CELL_IS, KIND_FORMULA)
        scale = kind in (KIND_SCALE2, KIND_SCALE3)
        self.combo_op.setVisible(is_cell_is)
        self.edit_val1.setVisible(classic)
        for widget in (self.preview_label, self.preview_box, self.btn_format):
            widget.setVisible(classic)
        self.lbl_colors.setVisible(scale or kind == KIND_DATA_BAR)
        self.btn_colors[0].setVisible(scale or kind == KIND_DATA_BAR)
        self.btn_colors[1].setVisible(scale)
        self.btn_colors[2].setVisible(kind == KIND_SCALE3)
        self.combo_icons.setVisible(kind == KIND_ICON_SET)
        self.chk_reverse.setVisible(kind == KIND_ICON_SET)
        self._update_color_buttons()
        self._on_op_changed()

    def _scale_stops(self) -> list[str]:
        kind = self.combo_type.currentData()
        if kind == KIND_SCALE3:
            return list(self.scale_colors)
        return [self.scale_colors[0], self.scale_colors[2]]

    def _update_color_buttons(self) -> None:
        kind = self.combo_type.currentData() if hasattr(self, "combo_type") else KIND_CELL_IS
        if kind == KIND_DATA_BAR:
            colors = [self.bar_color, self.bar_color, self.bar_color]
        elif kind == KIND_SCALE2:
            colors = [self.scale_colors[0], self.scale_colors[2], self.scale_colors[2]]
        else:
            colors = self.scale_colors
        for btn, col in zip(self.btn_colors, colors, strict=False):
            btn.setStyleSheet(f"background: {col}; border: 1px solid #7F9DB9;")

    def _pick_scale_color(self, index: int) -> None:
        kind = self.combo_type.currentData()
        if kind == KIND_DATA_BAR:
            current = self.bar_color
        elif kind == KIND_SCALE2 and index == 1:
            index = 2
            current = self.scale_colors[2]
        else:
            current = self.scale_colors[index]
        col = QColorDialog.getColor(QColor(current), self, safe_tr("Select Color"))
        if not col.isValid():
            return
        if kind == KIND_DATA_BAR:
            self.bar_color = col.name().upper()
        else:
            self.scale_colors[index] = col.name().upper()
        self._update_color_buttons()

    def _on_op_changed(self) -> None:
        is_cell_is = self.combo_type.currentData() == CFRuleType.CELL_IS.value
        op = self.combo_op.currentData()
        is_between = is_cell_is and op in (CFOp.BETWEEN.value, CFOp.NOT_BETWEEN.value)
        self.lbl_and.setVisible(is_between)
        self.edit_val2.setVisible(is_between)

    def _on_format_clicked(self) -> None:
        dlg = CFFormatDialog(
            fg_color=self.fg_color,
            bg_color=self.bg_color,
            bold=self.bold,
            italic=self.italic,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.fg_color, self.bg_color, self.bold, self.italic = dlg.values()
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
        kind = self.combo_type.currentData()
        if kind in (KIND_SCALE2, KIND_SCALE3):
            stops = self._scale_stops()
            cfvos = [CFVO(type="min")]
            if kind == KIND_SCALE3:
                cfvos.append(CFVO(type="percentile", val=50))
            cfvos.append(CFVO(type="max"))
            return CFRule(
                type=CFRuleType.COLOR_SCALE.value,
                priority=priority,
                color_scale=ColorScaleRule(cfvos=cfvos, colors=stops),
            )
        if kind == KIND_DATA_BAR:
            return CFRule(
                type=CFRuleType.DATA_BAR.value,
                priority=priority,
                data_bar=DataBarRule(
                    cfvos=[CFVO(type="min"), CFVO(type="max")], color=self.bar_color
                ),
            )
        if kind == KIND_ICON_SET:
            set_name = self.combo_icons.currentData()
            count = int(str(set_name)[0]) if str(set_name)[:1].isdigit() else 3
            cfvos = [CFVO(type="percent", val=round(100 * i / count)) for i in range(count)]
            return CFRule(
                type=CFRuleType.ICON_SET.value,
                priority=priority,
                icon_set=IconSetRule(
                    set_name=set_name, cfvos=cfvos, reverse=self.chk_reverse.isChecked()
                ),
            )
        rtype = kind
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
        kind = rule.type
        if rule.color_scale is not None:
            colors = list(rule.color_scale.colors)
            kind = KIND_SCALE3 if len(colors) >= 3 else KIND_SCALE2
            if len(colors) >= 3:
                self.scale_colors = colors[:3]
            elif len(colors) == 2:
                self.scale_colors = [colors[0], self.scale_colors[1], colors[1]]
        elif rule.data_bar is not None:
            kind = KIND_DATA_BAR
            self.bar_color = rule.data_bar.color
        elif rule.icon_set is not None:
            kind = KIND_ICON_SET
            icon_idx = self.combo_icons.findData(rule.icon_set.set_name)
            if icon_idx >= 0:
                self.combo_icons.setCurrentIndex(icon_idx)
            self.chk_reverse.setChecked(bool(rule.icon_set.reverse))
        idx = self.combo_type.findData(kind)
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


class CFFormatDialog(QDialog):
    """Format sub-dialog for a classic condition: font colour, style and fill."""

    def __init__(
        self,
        fg_color: str | None = None,
        bg_color: str | None = None,
        bold: bool = False,
        italic: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("Format Cells"))
        self.fg_color = fg_color
        self.bg_color = bg_color
        layout = QVBoxLayout(self)

        font_box = QGroupBox(safe_tr("Font"), self)
        font_layout = QHBoxLayout(font_box)
        self.chk_bold = QCheckBox(safe_tr("Bold"), font_box)
        self.chk_bold.setChecked(bool(bold))
        self.chk_italic = QCheckBox(safe_tr("Italic"), font_box)
        self.chk_italic.setChecked(bool(italic))
        self.btn_font_color = QPushButton(safe_tr("Color..."), font_box)
        self.btn_font_color.clicked.connect(self._pick_font_color)
        font_layout.addWidget(self.chk_bold)
        font_layout.addWidget(self.chk_italic)
        font_layout.addWidget(self.btn_font_color)
        layout.addWidget(font_box)

        fill_box = QGroupBox(safe_tr("Patterns"), self)
        fill_layout = QHBoxLayout(fill_box)
        self.btn_fill = QPushButton(safe_tr("Cell Shading..."), fill_box)
        self.btn_fill.clicked.connect(self._pick_fill)
        self.btn_clear = QPushButton(safe_tr("Clear"), fill_box)
        self.btn_clear.clicked.connect(self._clear)
        fill_layout.addWidget(self.btn_fill)
        fill_layout.addWidget(self.btn_clear)
        layout.addWidget(fill_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh()

    def _refresh(self) -> None:
        self.btn_font_color.setStyleSheet(f"color: {self.fg_color or '#000000'};")
        self.btn_fill.setStyleSheet(f"background: {self.bg_color or '#FFFFFF'};")

    def _pick_font_color(self) -> None:
        col = QColorDialog.getColor(
            QColor(self.fg_color or "#9C0006"), self, safe_tr("Font Color")
        )
        if col.isValid():
            self.fg_color = col.name().upper()
            self._refresh()

    def _pick_fill(self) -> None:
        col = QColorDialog.getColor(
            QColor(self.bg_color or "#FFC7CE"), self, safe_tr("Cell Shading")
        )
        if col.isValid():
            self.bg_color = col.name().upper()
            self._refresh()

    def _clear(self) -> None:
        self.fg_color = None
        self.bg_color = None
        self.chk_bold.setChecked(False)
        self.chk_italic.setChecked(False)
        self._refresh()

    def values(self) -> tuple[str | None, str | None, bool, bool]:
        return self.fg_color, self.bg_color, self.chk_bold.isChecked(), self.chk_italic.isChecked()


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
