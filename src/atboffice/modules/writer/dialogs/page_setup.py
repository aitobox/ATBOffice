"""Word 2003 classic Page Setup Dialog for Quire writer."""

from __future__ import annotations

import copy

from PySide6.QtCore import QCoreApplication, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.models.properties import (
    PAPER_SIZES,
    SectionProperties,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("PageSetupDialog", text)


class PagePreviewWidget(QWidget):
    """Live preview widget demonstrating page margins and orientation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(130)
        self.props = SectionProperties()

    def update_props(self, props: SectionProperties) -> None:
        self.props = copy.deepcopy(props)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor("#ECE9D8"))

        pw = max(100.0, float(self.props.pg_w))
        ph = max(100.0, float(self.props.pg_h))

        avail_w = self.width() - 30
        avail_h = self.height() - 20
        scale = min(avail_w / pw, avail_h / ph)

        draw_w = pw * scale
        draw_h = ph * scale
        ox = (self.width() - draw_w) / 2.0
        oy = (self.height() - draw_h) / 2.0

        # Draw page shadow & paper
        painter.fillRect(QRectF(ox + 3, oy + 3, draw_w, draw_h), QColor("#A0A0A0"))
        page_rect = QRectF(ox, oy, draw_w, draw_h)
        painter.fillRect(page_rect, Qt.GlobalColor.white)
        painter.setPen(QPen(QColor("#707070"), 1))
        painter.drawRect(page_rect)

        # Draw margins inside page
        ml = float(self.props.ml + self.props.gutter) * scale
        mr = float(self.props.mr) * scale
        mt = float(self.props.mt) * scale
        mb = float(self.props.mb) * scale

        cw = max(4.0, draw_w - ml - mr)
        ch = max(4.0, draw_h - mt - mb)
        content_rect = QRectF(ox + ml, oy + mt, cw, ch)
        dash_pen = QPen(QColor("#0066CC"), 1, Qt.PenStyle.DashLine)
        painter.setPen(dash_pen)
        painter.drawRect(content_rect)

        # Draw simulated text lines inside margins
        painter.setPen(QPen(QColor("#CCCCCC"), 1))
        cur_y = content_rect.top() + 4.0
        while cur_y < content_rect.bottom() - 3.0:
            painter.drawLine(content_rect.left() + 2.0, cur_y, content_rect.right() - 2.0, cur_y)
            cur_y += 6.0


class PageSetupDialog(QDialog):
    """Word 2003 classic Page Setup Dialog."""

    def __init__(
        self,
        props: SectionProperties | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.props = copy.deepcopy(props) if props is not None else SectionProperties()
        self.setMinimumWidth(500)
        self.setWindowTitle(safe_tr("页面设置"))

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        self.tab_widget = QTabWidget(self)

        # --- Tab 1: 页边距 (Margins) ---
        self.tab_margins = QWidget()
        m_tab_layout = QVBoxLayout(self.tab_margins)

        self.group_margins = QGroupBox(self.tab_margins)
        mg_grid = QGridLayout(self.group_margins)

        self.lbl_top = QLabel(self.group_margins)
        self.spin_top = QDoubleSpinBox(self.group_margins)
        self.spin_top.setRange(0.0, 1584.0)
        self.spin_top.setSuffix(" pt")

        self.lbl_bottom = QLabel(self.group_margins)
        self.spin_bottom = QDoubleSpinBox(self.group_margins)
        self.spin_bottom.setRange(0.0, 1584.0)
        self.spin_bottom.setSuffix(" pt")

        self.lbl_left = QLabel(self.group_margins)
        self.spin_left = QDoubleSpinBox(self.group_margins)
        self.spin_left.setRange(0.0, 1584.0)
        self.spin_left.setSuffix(" pt")

        self.lbl_right = QLabel(self.group_margins)
        self.spin_right = QDoubleSpinBox(self.group_margins)
        self.spin_right.setRange(0.0, 1584.0)
        self.spin_right.setSuffix(" pt")

        self.lbl_gutter = QLabel(self.group_margins)
        self.spin_gutter = QDoubleSpinBox(self.group_margins)
        self.spin_gutter.setRange(0.0, 1584.0)
        self.spin_gutter.setSuffix(" pt")

        self.lbl_gutter_pos = QLabel(self.group_margins)
        self.combo_gutter_pos = QComboBox(self.group_margins)
        self.combo_gutter_pos.addItem(safe_tr("左"), "left")
        self.combo_gutter_pos.addItem(safe_tr("上"), "top")

        mg_grid.addWidget(self.lbl_top, 0, 0)
        mg_grid.addWidget(self.spin_top, 0, 1)
        mg_grid.addWidget(self.lbl_bottom, 0, 2)
        mg_grid.addWidget(self.spin_bottom, 0, 3)

        mg_grid.addWidget(self.lbl_left, 1, 0)
        mg_grid.addWidget(self.spin_left, 1, 1)
        mg_grid.addWidget(self.lbl_right, 1, 2)
        mg_grid.addWidget(self.spin_right, 1, 3)

        mg_grid.addWidget(self.lbl_gutter, 2, 0)
        mg_grid.addWidget(self.spin_gutter, 2, 1)
        mg_grid.addWidget(self.lbl_gutter_pos, 2, 2)
        mg_grid.addWidget(self.combo_gutter_pos, 2, 3)
        m_tab_layout.addWidget(self.group_margins)

        # Orientation
        self.group_orientation = QGroupBox(self.tab_margins)
        orient_layout = QHBoxLayout(self.group_orientation)
        self.radio_portrait = QRadioButton(self.group_orientation)
        self.radio_landscape = QRadioButton(self.group_orientation)
        self.radio_portrait.setChecked(True)
        orient_group = QButtonGroup(self.group_orientation)
        orient_group.addButton(self.radio_portrait)
        orient_group.addButton(self.radio_landscape)
        orient_layout.addWidget(self.radio_portrait)
        orient_layout.addWidget(self.radio_landscape)
        orient_layout.addStretch()
        m_tab_layout.addWidget(self.group_orientation)

        self.tab_widget.addTab(self.tab_margins, safe_tr("页边距"))

        # --- Tab 2: 纸张 (Paper) ---
        self.tab_paper = QWidget()
        paper_layout = QFormLayout(self.tab_paper)

        self.lbl_paper_size = QLabel(self.tab_paper)
        self.combo_paper_size = QComboBox(self.tab_paper)
        for name in PAPER_SIZES:
            self.combo_paper_size.addItem(name, name)
        self.combo_paper_size.addItem(safe_tr("自定义大小"), "Custom")

        self.lbl_paper_width = QLabel(self.tab_paper)
        self.spin_paper_width = QDoubleSpinBox(self.tab_paper)
        self.spin_paper_width.setRange(10.0, 5000.0)
        self.spin_paper_width.setSuffix(" pt")

        self.lbl_paper_height = QLabel(self.tab_paper)
        self.spin_paper_height = QDoubleSpinBox(self.tab_paper)
        self.spin_paper_height.setRange(10.0, 5000.0)
        self.spin_paper_height.setSuffix(" pt")

        paper_layout.addRow(self.lbl_paper_size, self.combo_paper_size)
        paper_layout.addRow(self.lbl_paper_width, self.spin_paper_width)
        paper_layout.addRow(self.lbl_paper_height, self.spin_paper_height)

        self.tab_widget.addTab(self.tab_paper, safe_tr("纸张"))

        # --- Tab 3: 版式 (Layout) ---
        self.tab_layout = QWidget()
        lay_tab_layout = QVBoxLayout(self.tab_layout)

        # Section start
        self.group_section = QGroupBox(self.tab_layout)
        sec_layout = QFormLayout(self.group_section)
        self.lbl_section_start = QLabel(self.group_section)
        self.combo_section_start = QComboBox(self.group_section)
        self.combo_section_start.addItem(safe_tr("新建页"), "nextPage")
        self.combo_section_start.addItem(safe_tr("连续"), "continuous")
        self.combo_section_start.addItem(safe_tr("奇数页"), "oddPage")
        self.combo_section_start.addItem(safe_tr("偶数页"), "evenPage")
        sec_layout.addRow(self.lbl_section_start, self.combo_section_start)
        lay_tab_layout.addWidget(self.group_section)

        # Headers & footers
        self.group_hdr_ftr = QGroupBox(self.tab_layout)
        hf_grid = QGridLayout(self.group_hdr_ftr)
        self.check_odd_even = QCheckBox(self.group_hdr_ftr)
        self.check_first_page = QCheckBox(self.group_hdr_ftr)
        self.lbl_hdr_margin = QLabel(self.group_hdr_ftr)
        self.spin_hdr_margin = QDoubleSpinBox(self.group_hdr_ftr)
        self.spin_hdr_margin.setRange(0.0, 1584.0)
        self.spin_hdr_margin.setSuffix(" pt")

        self.lbl_ftr_margin = QLabel(self.group_hdr_ftr)
        self.spin_ftr_margin = QDoubleSpinBox(self.group_hdr_ftr)
        self.spin_ftr_margin.setRange(0.0, 1584.0)
        self.spin_ftr_margin.setSuffix(" pt")

        hf_grid.addWidget(self.check_odd_even, 0, 0, 1, 2)
        hf_grid.addWidget(self.check_first_page, 1, 0, 1, 2)
        hf_grid.addWidget(self.lbl_hdr_margin, 2, 0)
        hf_grid.addWidget(self.spin_hdr_margin, 2, 1)
        hf_grid.addWidget(self.lbl_ftr_margin, 2, 2)
        hf_grid.addWidget(self.spin_ftr_margin, 2, 3)
        lay_tab_layout.addWidget(self.group_hdr_ftr)

        # Vertical align
        self.group_page_align = QGroupBox(self.tab_layout)
        pa_layout = QFormLayout(self.group_page_align)
        self.lbl_v_align = QLabel(self.group_page_align)
        self.combo_v_align = QComboBox(self.group_page_align)
        self.combo_v_align.addItem(safe_tr("顶端对齐"), "top")
        self.combo_v_align.addItem(safe_tr("居中"), "center")
        self.combo_v_align.addItem(safe_tr("两端对齐"), "both")
        self.combo_v_align.addItem(safe_tr("底端对齐"), "bottom")
        pa_layout.addRow(self.lbl_v_align, self.combo_v_align)
        lay_tab_layout.addWidget(self.group_page_align)

        self.tab_widget.addTab(self.tab_layout, safe_tr("版式"))
        main_layout.addWidget(self.tab_widget)

        # Preview Group
        self.group_preview = QGroupBox(self)
        prev_layout = QVBoxLayout(self.group_preview)
        self.preview_widget = PagePreviewWidget(self.group_preview)
        prev_layout.addWidget(self.preview_widget)
        main_layout.addWidget(self.group_preview)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # Event triggers
        self._updating_controls = False
        self._connect_triggers()
        self._load_from_props()
        self.retranslate_ui()

    def _connect_triggers(self) -> None:
        self.combo_paper_size.currentIndexChanged.connect(self._on_paper_size_preset_changed)
        self.spin_paper_width.valueChanged.connect(self._on_dimension_spin_changed)
        self.spin_paper_height.valueChanged.connect(self._on_dimension_spin_changed)

        self.radio_portrait.toggled.connect(self._on_orientation_toggled)
        self.radio_landscape.toggled.connect(self._on_orientation_toggled)

        for spin in [
            self.spin_top, self.spin_bottom, self.spin_left, self.spin_right,
            self.spin_gutter, self.spin_hdr_margin, self.spin_ftr_margin
        ]:
            spin.valueChanged.connect(self._trigger_preview)

        self.combo_v_align.currentIndexChanged.connect(self._trigger_preview)

    def _on_paper_size_preset_changed(self) -> None:
        if self._updating_controls:
            return
        size_name = self.combo_paper_size.currentData()
        if size_name in PAPER_SIZES:
            w, h = PAPER_SIZES[size_name]
            self._updating_controls = True
            if self.radio_landscape.isChecked():
                self.spin_paper_width.setValue(max(w, h))
                self.spin_paper_height.setValue(min(w, h))
            else:
                self.spin_paper_width.setValue(min(w, h))
                self.spin_paper_height.setValue(max(w, h))
            self._updating_controls = False
            self._trigger_preview()

    def _on_dimension_spin_changed(self) -> None:
        if self._updating_controls:
            return
        w = self.spin_paper_width.value()
        h = self.spin_paper_height.value()

        # Check if matches any preset
        matched = False
        for name, (pw, ph) in PAPER_SIZES.items():
            matches_normal = abs(w - pw) < 0.5 and abs(h - ph) < 0.5
            matches_swapped = abs(w - ph) < 0.5 and abs(h - pw) < 0.5
            if matches_normal or matches_swapped:
                idx = self.combo_paper_size.findData(name)
                if idx >= 0:
                    self._updating_controls = True
                    self.combo_paper_size.setCurrentIndex(idx)
                    self._updating_controls = False
                    matched = True
                    break
        if not matched:
            idx = self.combo_paper_size.findData("Custom")
            if idx >= 0:
                self._updating_controls = True
                self.combo_paper_size.setCurrentIndex(idx)
                self._updating_controls = False

        self._trigger_preview()

    def _on_orientation_toggled(self) -> None:
        if self._updating_controls:
            return
        w = self.spin_paper_width.value()
        h = self.spin_paper_height.value()
        self._updating_controls = True
        if self.radio_landscape.isChecked() and w < h:
            self.spin_paper_width.setValue(h)
            self.spin_paper_height.setValue(w)
        elif self.radio_portrait.isChecked() and w > h:
            self.spin_paper_width.setValue(h)
            self.spin_paper_height.setValue(w)
        self._updating_controls = False
        self._trigger_preview()

    def _trigger_preview(self) -> None:
        updated = self.get_properties()
        self.preview_widget.update_props(updated)

    def _load_from_props(self) -> None:
        self._updating_controls = True
        # Margins
        self.spin_top.setValue(float(self.props.mt))
        self.spin_bottom.setValue(float(self.props.mb))
        self.spin_left.setValue(float(self.props.ml))
        self.spin_right.setValue(float(self.props.mr))
        self.spin_gutter.setValue(float(self.props.gutter))

        # Orientation & Paper Dimensions
        w = float(self.props.pg_w)
        h = float(self.props.pg_h)
        is_landscape = self.props.orient == "landscape" or w > h
        if is_landscape:
            self.radio_landscape.setChecked(True)
        else:
            self.radio_portrait.setChecked(True)

        self.spin_paper_width.setValue(w)
        self.spin_paper_height.setValue(h)

        # Preset match
        matched_idx = -1
        for i in range(self.combo_paper_size.count()):
            d = self.combo_paper_size.itemData(i)
            if d in PAPER_SIZES:
                pw, ph = PAPER_SIZES[d]
                matches_normal = abs(w - pw) < 0.5 and abs(h - ph) < 0.5
            matches_swapped = abs(w - ph) < 0.5 and abs(h - pw) < 0.5
            if matches_normal or matches_swapped:
                    matched_idx = i
                    break
        if matched_idx >= 0:
            self.combo_paper_size.setCurrentIndex(matched_idx)
        else:
            c_idx = self.combo_paper_size.findData("Custom")
            if c_idx >= 0:
                self.combo_paper_size.setCurrentIndex(c_idx)

        # Layout
        st_idx = self.combo_section_start.findData(self.props.sect_type or "nextPage")
        if st_idx >= 0:
            self.combo_section_start.setCurrentIndex(st_idx)

        self.check_first_page.setChecked(bool(self.props.title_pg))
        self.spin_hdr_margin.setValue(float(self.props.hdr))
        self.spin_ftr_margin.setValue(float(self.props.ftr))

        va_idx = self.combo_v_align.findData(self.props.v_align or "top")
        if va_idx >= 0:
            self.combo_v_align.setCurrentIndex(va_idx)

        self._updating_controls = False
        self._trigger_preview()

    def get_properties(self) -> SectionProperties:
        """Construct updated SectionProperties from dialog controls."""
        res = copy.deepcopy(self.props)
        res.mt = self.spin_top.value()
        res.mb = self.spin_bottom.value()
        res.ml = self.spin_left.value()
        res.mr = self.spin_right.value()
        res.gutter = self.spin_gutter.value()

        res.orient = "landscape" if self.radio_landscape.isChecked() else "portrait"
        res.pg_w = self.spin_paper_width.value()
        res.pg_h = self.spin_paper_height.value()

        res.sect_type = self.combo_section_start.currentData() or "nextPage"
        res.title_pg = self.check_first_page.isChecked()
        res.hdr = self.spin_hdr_margin.value()
        res.ftr = self.spin_ftr_margin.value()
        res.v_align = self.combo_v_align.currentData() or "top"

        return res

    def retranslate_ui(self) -> None:
        """Localize UI strings."""
        self.setWindowTitle(safe_tr("页面设置"))
        self.tab_widget.setTabText(0, safe_tr("页边距"))
        self.tab_widget.setTabText(1, safe_tr("纸张"))
        self.tab_widget.setTabText(2, safe_tr("版式"))

        self.group_margins.setTitle(safe_tr("页边距"))
        self.lbl_top.setText(safe_tr("上(&T):"))
        self.lbl_bottom.setText(safe_tr("下(&B):"))
        self.lbl_left.setText(safe_tr("左(&L):"))
        self.lbl_right.setText(safe_tr("右(&R):"))
        self.lbl_gutter.setText(safe_tr("装订线(&G):"))
        self.lbl_gutter_pos.setText(safe_tr("装订线位置(&U):"))

        self.group_orientation.setTitle(safe_tr("方向"))
        self.radio_portrait.setText(safe_tr("纵向(&P)"))
        self.radio_landscape.setText(safe_tr("横向(&S)"))

        self.lbl_paper_size.setText(safe_tr("纸张大小(&Z):"))
        self.lbl_paper_width.setText(safe_tr("宽度(&W):"))
        self.lbl_paper_height.setText(safe_tr("高度(&H):"))

        self.group_section.setTitle(safe_tr("节"))
        self.lbl_section_start.setText(safe_tr("节的起始位置(&R):"))

        self.group_hdr_ftr.setTitle(safe_tr("页眉和页脚"))
        self.check_odd_even.setText(safe_tr("奇偶页不同(&O)"))
        self.check_first_page.setText(safe_tr("首页不同(&F)"))
        self.lbl_hdr_margin.setText(safe_tr("距边界: 页眉(&H):"))
        self.lbl_ftr_margin.setText(safe_tr("页脚(&F):"))

        self.group_page_align.setTitle(safe_tr("页面"))
        self.lbl_v_align.setText(safe_tr("垂直对齐方式(&V):"))

        self.group_preview.setTitle(safe_tr("预览"))
