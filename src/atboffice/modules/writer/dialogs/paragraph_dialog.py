"""Word 2003 classic Paragraph Dialog for Quire writer."""

from __future__ import annotations

import copy

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.models.properties import (
    IndentProperties,
    ParagraphProperties,
    SpacingProperties,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("ParagraphDialog", text)


class ParagraphPreviewWidget(QWidget):
    """Live preview widget demonstrating paragraph alignment, indents, and spacing."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(110)
        self.props = ParagraphProperties()

    def update_props(self, props: ParagraphProperties) -> None:
        self.props = copy.deepcopy(props)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Border & background
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        painter.setPen(QPen(QColor("#B0B0B0"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        margin_x = 24
        content_w = max(40, self.width() - margin_x * 2)

        # Draw preceding paragraph simulation (gray)
        painter.setPen(QPen(QColor("#D0D0D0"), 2))
        painter.drawLine(margin_x, 15, margin_x + int(content_w * 0.9), 15)
        painter.drawLine(margin_x, 23, margin_x + int(content_w * 0.7), 23)

        # Active paragraph layout calculation
        ind = self.props.ind
        sp = self.props.sp
        left_px = max(0, int(ind.left * 0.5))
        right_px = max(0, int(ind.right * 0.5))
        first_px = int(ind.first_line * 0.5)

        base_y = 35 + max(0, int(sp.before * 0.3))
        line_spacing_px = max(6, int(10 * (sp.line if sp.line_rule == "auto" else 1.0)))

        painter.setPen(QPen(QColor("#104080"), 2))

        # First line
        f_left = margin_x + left_px + (first_px if first_px > 0 else 0)
        f_right = margin_x + content_w - right_px
        if self.props.jc == "center":
            offset = 15
            painter.drawLine(margin_x + offset, base_y, margin_x + content_w - offset, base_y)
        elif self.props.jc == "right":
            painter.drawLine(f_right - int(content_w * 0.8), base_y, f_right, base_y)
        else:
            painter.drawLine(f_left, base_y, f_right, base_y)

        # Body line 2
        b_left = margin_x + left_px + (abs(first_px) if first_px < 0 else 0)
        b_right = margin_x + content_w - right_px
        y2 = base_y + line_spacing_px
        painter.drawLine(b_left, y2, b_right, y2)

        # Body line 3 (shorter)
        y3 = y2 + line_spacing_px
        p_len = int((b_right - b_left) * 0.6)
        painter.drawLine(b_left, y3, b_left + p_len, y3)

        # Following paragraph simulation (gray)
        post_y = y3 + 12 + max(0, int(sp.after * 0.3))
        if post_y < self.height() - 8:
            painter.setPen(QPen(QColor("#D0D0D0"), 2))
            painter.drawLine(margin_x, post_y, margin_x + int(content_w * 0.85), post_y)


class ParagraphDialog(QDialog):
    """Word 2003 classic Paragraph Dialog."""

    def __init__(
        self,
        props: ParagraphProperties | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.props = copy.deepcopy(props) if props is not None else ParagraphProperties()
        self.setMinimumWidth(480)
        self.setWindowTitle(safe_tr("段落"))

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        self.tab_widget = QTabWidget(self)

        # --- Tab 1: 缩进和间距 (Indents and Spacing) ---
        self.tab_indents = QWidget()
        ind_tab_layout = QVBoxLayout(self.tab_indents)

        # 1. 常规 (General)
        self.group_general = QGroupBox(self.tab_indents)
        gen_grid = QGridLayout(self.group_general)

        self.lbl_align = QLabel(self.group_general)
        self.combo_align = QComboBox(self.group_general)
        self.combo_align.addItem(safe_tr("左对齐"), "left")
        self.combo_align.addItem(safe_tr("居中"), "center")
        self.combo_align.addItem(safe_tr("右对齐"), "right")
        self.combo_align.addItem(safe_tr("两端对齐"), "both")
        self.combo_align.addItem(safe_tr("分散对齐"), "distribute")

        self.lbl_outline = QLabel(self.group_general)
        self.combo_outline = QComboBox(self.group_general)
        self.combo_outline.addItem(safe_tr("正文文本"), None)
        for i in range(1, 10):
            self.combo_outline.addItem(safe_tr(f"{i} 级"), i)

        gen_grid.addWidget(self.lbl_align, 0, 0)
        gen_grid.addWidget(self.combo_align, 0, 1)
        gen_grid.addWidget(self.lbl_outline, 0, 2)
        gen_grid.addWidget(self.combo_outline, 0, 3)
        ind_tab_layout.addWidget(self.group_general)

        # 2. 缩进 (Indentation)
        self.group_indent = QGroupBox(self.tab_indents)
        ind_grid = QGridLayout(self.group_indent)

        self.lbl_indent_left = QLabel(self.group_indent)
        self.spin_indent_left = QDoubleSpinBox(self.group_indent)
        self.spin_indent_left.setRange(-1584.0, 1584.0)
        self.spin_indent_left.setSingleStep(1.0)
        self.spin_indent_left.setSuffix(" pt")

        self.lbl_indent_right = QLabel(self.group_indent)
        self.spin_indent_right = QDoubleSpinBox(self.group_indent)
        self.spin_indent_right.setRange(-1584.0, 1584.0)
        self.spin_indent_right.setSingleStep(1.0)
        self.spin_indent_right.setSuffix(" pt")

        self.lbl_indent_special = QLabel(self.group_indent)
        self.combo_indent_special = QComboBox(self.group_indent)
        self.combo_indent_special.addItem(safe_tr("(无)"), "none")
        self.combo_indent_special.addItem(safe_tr("首行缩进"), "first")
        self.combo_indent_special.addItem(safe_tr("悬挂缩进"), "hanging")

        self.lbl_indent_by = QLabel(self.group_indent)
        self.spin_indent_by = QDoubleSpinBox(self.group_indent)
        self.spin_indent_by.setRange(0.0, 1584.0)
        self.spin_indent_by.setSingleStep(1.0)
        self.spin_indent_by.setValue(21.0)
        self.spin_indent_by.setSuffix(" pt")

        ind_grid.addWidget(self.lbl_indent_left, 0, 0)
        ind_grid.addWidget(self.spin_indent_left, 0, 1)
        ind_grid.addWidget(self.lbl_indent_special, 0, 2)
        ind_grid.addWidget(self.combo_indent_special, 0, 3)
        ind_grid.addWidget(self.lbl_indent_right, 1, 0)
        ind_grid.addWidget(self.spin_indent_right, 1, 1)
        ind_grid.addWidget(self.lbl_indent_by, 1, 2)
        ind_grid.addWidget(self.spin_indent_by, 1, 3)
        ind_tab_layout.addWidget(self.group_indent)

        # 3. 间距 (Spacing)
        self.group_spacing = QGroupBox(self.tab_indents)
        sp_grid = QGridLayout(self.group_spacing)

        self.lbl_space_before = QLabel(self.group_spacing)
        self.spin_space_before = QDoubleSpinBox(self.group_spacing)
        self.spin_space_before.setRange(0.0, 1584.0)
        self.spin_space_before.setSingleStep(1.0)
        self.spin_space_before.setSuffix(" pt")

        self.lbl_space_after = QLabel(self.group_spacing)
        self.spin_space_after = QDoubleSpinBox(self.group_spacing)
        self.spin_space_after.setRange(0.0, 1584.0)
        self.spin_space_after.setSingleStep(1.0)
        self.spin_space_after.setSuffix(" pt")

        self.lbl_line_spacing = QLabel(self.group_spacing)
        self.combo_line_spacing = QComboBox(self.group_spacing)
        self.combo_line_spacing.addItem(safe_tr("单倍行距"), ("auto", 1.0))
        self.combo_line_spacing.addItem(safe_tr("1.5 倍行距"), ("auto", 1.5))
        self.combo_line_spacing.addItem(safe_tr("2 倍行距"), ("auto", 2.0))
        self.combo_line_spacing.addItem(safe_tr("最小值"), ("atLeast", 12.0))
        self.combo_line_spacing.addItem(safe_tr("固定值"), ("exact", 12.0))
        self.combo_line_spacing.addItem(safe_tr("多倍行距"), ("auto", 1.25))

        self.lbl_line_spacing_at = QLabel(self.group_spacing)
        self.spin_line_spacing_at = QDoubleSpinBox(self.group_spacing)
        self.spin_line_spacing_at.setRange(0.0, 1584.0)
        self.spin_line_spacing_at.setSingleStep(0.25)
        self.spin_line_spacing_at.setValue(1.0)

        sp_grid.addWidget(self.lbl_space_before, 0, 0)
        sp_grid.addWidget(self.spin_space_before, 0, 1)
        sp_grid.addWidget(self.lbl_line_spacing, 0, 2)
        sp_grid.addWidget(self.combo_line_spacing, 0, 3)
        sp_grid.addWidget(self.lbl_space_after, 1, 0)
        sp_grid.addWidget(self.spin_space_after, 1, 1)
        sp_grid.addWidget(self.lbl_line_spacing_at, 1, 2)
        sp_grid.addWidget(self.spin_line_spacing_at, 1, 3)
        ind_tab_layout.addWidget(self.group_spacing)

        self.tab_widget.addTab(self.tab_indents, safe_tr("缩进和间距"))

        # --- Tab 2: 换行和分页 (Line and Page Breaks) ---
        self.tab_breaks = QWidget()
        breaks_layout = QVBoxLayout(self.tab_breaks)

        self.group_pagination = QGroupBox(self.tab_breaks)
        pag_layout = QVBoxLayout(self.group_pagination)
        self.check_widow_control = QCheckBox(self.group_pagination)
        self.check_keep_next = QCheckBox(self.group_pagination)
        self.check_keep_lines = QCheckBox(self.group_pagination)
        self.check_page_break_before = QCheckBox(self.group_pagination)

        pag_layout.addWidget(self.check_widow_control)
        pag_layout.addWidget(self.check_keep_next)
        pag_layout.addWidget(self.check_keep_lines)
        pag_layout.addWidget(self.check_page_break_before)
        breaks_layout.addWidget(self.group_pagination)
        breaks_layout.addStretch()

        self.tab_widget.addTab(self.tab_breaks, safe_tr("换行和分页"))
        main_layout.addWidget(self.tab_widget)

        # Preview Group
        self.group_preview = QGroupBox(self)
        prev_layout = QVBoxLayout(self.group_preview)
        self.preview_widget = ParagraphPreviewWidget(self.group_preview)
        prev_layout.addWidget(self.preview_widget)
        main_layout.addWidget(self.group_preview)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        self.btn_tabs = QPushButton(safe_tr("制表位(&T)..."), self)
        self.btn_tabs.clicked.connect(self._on_tabs_clicked)
        btn_layout.addWidget(self.btn_tabs)
        btn_layout.addStretch()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        btn_layout.addWidget(self.button_box)
        main_layout.addLayout(btn_layout)

        # Live Preview & interactions
        self._connect_triggers()
        self._load_from_props()
        self.retranslate_ui()

    def _connect_triggers(self) -> None:
        self.combo_align.currentIndexChanged.connect(self._trigger_preview)
        self.combo_indent_special.currentIndexChanged.connect(self._on_special_indent_changed)
        self.combo_line_spacing.currentIndexChanged.connect(self._on_line_spacing_changed)

        for spin in [
            self.spin_indent_left,
            self.spin_indent_right,
            self.spin_indent_by,
            self.spin_space_before,
            self.spin_space_after,
            self.spin_line_spacing_at,
        ]:
            spin.valueChanged.connect(self._trigger_preview)

    def _on_special_indent_changed(self) -> None:
        mode = self.combo_indent_special.currentData()
        self.spin_indent_by.setEnabled(mode != "none")
        self._trigger_preview()

    def _on_line_spacing_changed(self) -> None:
        rule, default_val = self.combo_line_spacing.currentData()
        self.spin_line_spacing_at.setValue(default_val)
        if rule == "exact" or rule == "atLeast":
            self.spin_line_spacing_at.setSuffix(" pt")
        else:
            self.spin_line_spacing_at.setSuffix("")
        self._trigger_preview()

    def _trigger_preview(self) -> None:
        props = self.get_properties()
        self.preview_widget.update_props(props)

    def _load_from_props(self) -> None:
        # Align
        idx = self.combo_align.findData(self.props.jc or "left")
        if idx >= 0:
            self.combo_align.setCurrentIndex(idx)

        # Outline
        lvl = self.props.outline_level
        idx = self.combo_outline.findData(lvl)
        if idx >= 0:
            self.combo_outline.setCurrentIndex(idx)

        # Indent
        ind = self.props.ind or IndentProperties()
        self.spin_indent_left.setValue(ind.left)
        self.spin_indent_right.setValue(ind.right)
        if ind.first_line > 0:
            self.combo_indent_special.setCurrentIndex(1)  # first
            self.spin_indent_by.setValue(ind.first_line)
        elif ind.first_line < 0:
            self.combo_indent_special.setCurrentIndex(2)  # hanging
            self.spin_indent_by.setValue(abs(ind.first_line))
        else:
            self.combo_indent_special.setCurrentIndex(0)  # none

        # Spacing
        sp = self.props.sp or SpacingProperties()
        self.spin_space_before.setValue(sp.before)
        self.spin_space_after.setValue(sp.after)

        # Line spacing
        if sp.line_rule == "exact":
            self.combo_line_spacing.setCurrentIndex(4)
        elif sp.line_rule == "atLeast":
            self.combo_line_spacing.setCurrentIndex(3)
        elif abs(sp.line - 1.5) < 0.05:
            self.combo_line_spacing.setCurrentIndex(1)
        elif abs(sp.line - 2.0) < 0.05:
            self.combo_line_spacing.setCurrentIndex(2)
        elif abs(sp.line - 1.0) < 0.05:
            self.combo_line_spacing.setCurrentIndex(0)
        else:
            self.combo_line_spacing.setCurrentIndex(5)
        self.spin_line_spacing_at.setValue(sp.line)

        # Pagination
        self.check_widow_control.setChecked(bool(self.props.widow_control))
        self.check_keep_next.setChecked(bool(self.props.keep_next))
        self.check_keep_lines.setChecked(bool(self.props.keep_lines))
        self.check_page_break_before.setChecked(bool(self.props.page_break_before))

        self._trigger_preview()

    def _on_tabs_clicked(self) -> None:
        """Launch classic Tabs dialog and synchronize tab stops."""
        from atboffice.modules.writer.dialogs.tabs_dialog import TabsDialog

        dlg = TabsDialog(parent=self, tabs=self.props.tabs)
        if dlg.exec():
            self.props.tabs = dlg.get_tabs()
            self._trigger_preview()

    def get_properties(self) -> ParagraphProperties:
        """Construct updated ParagraphProperties from dialog controls."""
        res = copy.deepcopy(self.props)
        res.jc = self.combo_align.currentData() or "left"
        res.outline_level = self.combo_outline.currentData()

        # Indent
        left = self.spin_indent_left.value()
        right = self.spin_indent_right.value()
        mode = self.combo_indent_special.currentData()
        if mode == "first":
            first_line = self.spin_indent_by.value()
        elif mode == "hanging":
            first_line = -self.spin_indent_by.value()
        else:
            first_line = 0.0
        res.ind = IndentProperties(left=left, right=right, first_line=first_line)

        # Spacing
        before = self.spin_space_before.value()
        after = self.spin_space_after.value()
        rule, _ = self.combo_line_spacing.currentData()
        line = self.spin_line_spacing_at.value()
        res.sp = SpacingProperties(before=before, after=after, line=line, line_rule=rule)

        # Pagination
        res.widow_control = self.check_widow_control.isChecked()
        res.keep_next = self.check_keep_next.isChecked()
        res.keep_lines = self.check_keep_lines.isChecked()
        res.page_break_before = self.check_page_break_before.isChecked()

        return res

    def retranslate_ui(self) -> None:
        """Localize UI strings."""
        self.setWindowTitle(safe_tr("段落"))
        self.tab_widget.setTabText(0, safe_tr("缩进和间距"))
        self.tab_widget.setTabText(1, safe_tr("换行和分页"))

        self.group_general.setTitle(safe_tr("常规"))
        self.lbl_align.setText(safe_tr("对齐方式(&G):"))
        self.lbl_outline.setText(safe_tr("大纲级别(&O):"))

        self.group_indent.setTitle(safe_tr("缩进"))
        self.lbl_indent_left.setText(safe_tr("左侧(&L):"))
        self.lbl_indent_right.setText(safe_tr("右侧(&R):"))
        self.lbl_indent_special.setText(safe_tr("特殊格式(&S):"))
        self.lbl_indent_by.setText(safe_tr("度量值(&B):"))

        self.group_spacing.setTitle(safe_tr("间距"))
        self.lbl_space_before.setText(safe_tr("段前(&B):"))
        self.lbl_space_after.setText(safe_tr("段后(&A):"))
        self.lbl_line_spacing.setText(safe_tr("行距(&N):"))
        self.lbl_line_spacing_at.setText(safe_tr("设置值(&T):"))

        self.group_pagination.setTitle(safe_tr("分页"))
        self.check_widow_control.setText(safe_tr("孤行控制(&W)"))
        self.check_keep_next.setText(safe_tr("与下段同页(&K)"))
        self.check_keep_lines.setText(safe_tr("段中不分页(&L)"))
        self.check_page_break_before.setText(safe_tr("段前分页(&P)"))

        self.group_preview.setTitle(safe_tr("预览"))
        self.btn_tabs.setText(safe_tr("制表位(&T)..."))
