"""Slide Master View (幻灯片母版视图) for Lectern presentations.

Provides:
- Authentic PowerPoint 2003 Slide Master editing environment.
- Dedicated master close toolbar with "Close Master View",
  "Insert Title Master", and "Delete Title Master".
- Left-hand master hierarchy list (Slide Master / Title Master).
- Full WYSIWYG master canvas showing title, multi-level body, and footer placeholders.
- Seamless synchronization with presentation DesignTemplate on close.
- 100% i18n support with safe_tr and retranslate_ui.
"""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import safe_tr
from atboffice.modules.presentation.models.presentation import (
    VALID_HANDOUT_COUNTS,
    Presentation,
)
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.printing import (
    FOOTER_H,
    HEADER_H,
    MARGIN,
    _fit,
    handout_slots,
)
from atboffice.modules.presentation.views.slide_canvas import (
    SlideCanvasView,
    SlideScene,
)
from atboffice.modules.presentation.views.workspace import (
    build_master_slide,
    render_slide_thumbnail,
    sync_master_slide,
)
from atboffice.ui.printing.printer_setup import A4_PT
from atboffice.ui.styles.luna_2003 import ui_font


class MasterCloseBar(QToolBar):
    """Floating/docked toolbar shown exclusively in Slide Master View."""

    close_clicked = Signal()
    insert_title_master_clicked = Signal()
    delete_title_master_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("幻灯片母版视图"))
        self.setMovable(False)
        self.setStyleSheet(
            """
            QToolBar {
                background-color: #F0F0F0;
                border-bottom: 1px solid #C0C0C0;
                padding: 4px;
                spacing: 8px;
            }
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #ABABAB;
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 12px;
                color: #222222;
            }
            QPushButton:hover {
                background-color: #DCE6F1;
                border: 1px solid #2B579A;
            }
            QPushButton#btnClose {
                background-color: #2B579A;
                color: #FFFFFF;
                font-weight: bold;
                border: 1px solid #1E3F6F;
            }
            QPushButton#btnClose:hover {
                background-color: #1E3F6F;
            }
            """
        )

        self.lbl_title = QLabel(safe_tr("幻灯片母版视图"), self)
        self.lbl_title.setFont(ui_font(9, bold=True))
        self.lbl_title.setStyleSheet("color: #333333; margin-right: 12px;")
        self.addWidget(self.lbl_title)

        self.btn_insert = QPushButton(safe_tr("插入新标题母版"), self)
        self.btn_insert.clicked.connect(self.insert_title_master_clicked.emit)
        self.addWidget(self.btn_insert)

        self.btn_delete = QPushButton(safe_tr("删除标题母版"), self)
        self.btn_delete.clicked.connect(self.delete_title_master_clicked.emit)
        self.addWidget(self.btn_delete)

        # Spacer to push close button to the right
        spacer = QWidget(self)
        spacer.setSizePolicy(
            QPushButton.sizePolicy(self.btn_insert).horizontalPolicy(),
            QPushButton.sizePolicy(self.btn_insert).verticalPolicy(),
        )
        self.addWidget(spacer)

        self.btn_close = QPushButton(safe_tr("关闭母版视图"), self)
        self.btn_close.setObjectName("btnClose")
        self.btn_close.clicked.connect(self.close_clicked.emit)
        self.addWidget(self.btn_close)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("幻灯片母版视图"))
        self.lbl_title.setText(safe_tr("幻灯片母版视图"))
        self.btn_insert.setText(safe_tr("插入新标题母版"))
        self.btn_delete.setText(safe_tr("删除标题母版"))
        self.btn_close.setText(safe_tr("关闭母版视图"))


class SlideMasterView(QWidget):
    """Full Slide Master editing view with hierarchy pane and slide canvas."""

    close_requested = Signal()
    master_changed = Signal(str)

    def __init__(
        self,
        presentation: Presentation | None = None,
        parent: QWidget | None = None,
        scene: SlideScene | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation or Presentation()
        # With a shared scene (the workspace's), window-level editing commands act on the
        # master being edited; the scene is only loaded while this view is active.
        self._shared_scene = scene is not None
        self.master_kind: str = "slide"  # "slide" or "title"
        self.master_slide: Slide | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Top Close Toolbar
        self.toolbar = MasterCloseBar(self)
        self.toolbar.close_clicked.connect(self.close_master_view)
        self.toolbar.insert_title_master_clicked.connect(self.insert_title_master)
        self.toolbar.delete_title_master_clicked.connect(self.delete_title_master)
        layout.addWidget(self.toolbar)

        # 2. Main Area: Left Hierarchy Tree + Right Canvas
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setHandleWidth(2)
        self.splitter.setStyleSheet(
            """
            QSplitter::handle {
                background-color: #B0B0B0;
            }
            """
        )

        # Left pane: Master thumbnail list
        self.left_pane = QWidget(self.splitter)
        left_layout = QVBoxLayout(self.left_pane)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.setSpacing(4)

        self.lbl_left_title = QLabel(safe_tr("母版样式"), self.left_pane)
        self.lbl_left_title.setFont(ui_font(9, bold=True))
        self.lbl_left_title.setStyleSheet("color: #444444; padding: 2px 4px;")
        left_layout.addWidget(self.lbl_left_title)

        self.master_list = QListWidget(self.left_pane)
        self.master_list.setIconSize(QSize(140, 105))
        self.master_list.setSpacing(4)
        self.master_list.setStyleSheet(
            """
            QListWidget {
                background-color: #ECECEC;
                border: 1px solid #D0D0D0;
                outline: none;
            }
            QListWidget::item {
                background-color: #FFFFFF;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 4px;
                margin: 2px;
            }
            QListWidget::item:selected {
                background-color: #DCE6F1;
                border: 2px solid #2B579A;
                color: #000000;
            }
            """
        )
        self.master_list.currentRowChanged.connect(self._on_master_row_changed)
        left_layout.addWidget(self.master_list)
        self.left_pane.setFixedWidth(200)
        self.splitter.addWidget(self.left_pane)

        # Right pane: Master Slide Canvas
        self.canvas_container = QWidget(self.splitter)
        c_layout = QVBoxLayout(self.canvas_container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)

        self.scene = scene if scene is not None else SlideScene(parent=self)
        self.canvas_view = SlideCanvasView(self.scene, parent=self.canvas_container)
        c_layout.addWidget(self.canvas_view)
        self.splitter.addWidget(self.canvas_container)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        layout.addWidget(self.splitter)

        self.load_presentation(self.presentation)

    def load_presentation(self, presentation: Presentation) -> None:
        """Load presentation document and prepare master slide."""
        self.presentation = presentation
        self.master_slide = None
        self.master_kind = "slide"
        self.refresh_master_list()
        if not self._shared_scene:
            self.set_master_kind("slide")

    def refresh_master_list(self) -> None:
        """Populate left hierarchy list with slide master and title master."""
        self.master_list.blockSignals(True)
        self.master_list.clear()

        design = self.presentation.get_design_for_slide(None)

        # 1. Slide Master Item
        sm = build_master_slide(self.presentation, design, master_kind="slide")
        sm_pix = render_slide_thumbnail(sm, self.presentation, width=140)
        item_sm = QListWidgetItem(QIcon(sm_pix), safe_tr("1. 幻灯片母版"))
        item_sm.setSizeHint(QSize(170, sm_pix.height() + 28))
        self.master_list.addItem(item_sm)

        # 2. Title Master Item (if available or standard)
        has_title_master = design.title_decorations is not None or design.title_bg is not None
        self.toolbar.btn_delete.setEnabled(has_title_master)
        self.toolbar.btn_insert.setEnabled(not has_title_master)

        tm = build_master_slide(self.presentation, design, master_kind="title")
        tm_pix = render_slide_thumbnail(tm, self.presentation, width=140)
        item_tm = QListWidgetItem(QIcon(tm_pix), safe_tr("2. 标题母版"))
        item_tm.setSizeHint(QSize(170, tm_pix.height() + 28))
        self.master_list.addItem(item_tm)

        cur_row = 1 if self.master_kind == "title" else 0
        self.master_list.setCurrentRow(cur_row)
        self.master_list.blockSignals(False)

    def set_master_kind(self, kind: str) -> None:
        """Switch active master editing target between 'slide' and 'title'."""
        if self.master_slide:
            sync_master_slide(self.presentation, self.master_slide)

        self.master_kind = kind if kind in ("slide", "title") else "slide"
        design = self.presentation.get_design_for_slide(None)
        self.master_slide = build_master_slide(
            self.presentation, design, master_kind=self.master_kind
        )
        self.scene.load_slide(self.master_slide)
        self.canvas_view.zoom_fit()

        self.master_list.blockSignals(True)
        self.master_list.setCurrentRow(1 if self.master_kind == "title" else 0)
        self.master_list.blockSignals(False)
        self.master_changed.emit(self.master_kind)

    def _on_master_row_changed(self, row: int) -> None:
        new_kind = "title" if row == 1 else "slide"
        if new_kind != self.master_kind:
            self.set_master_kind(new_kind)

    def insert_title_master(self) -> None:
        """Create and attach dedicated title master to active design."""
        design = self.presentation.get_design_for_slide(None)
        if design.title_decorations is None:
            design.title_decorations = [copy.deepcopy(d) for d in design.decorations]
        self.refresh_master_list()
        self.set_master_kind("title")

    def delete_title_master(self) -> None:
        """Remove dedicated title master from active design."""
        design = self.presentation.get_design_for_slide(None)
        design.title_decorations = None
        design.title_bg = None
        # Do not sync the deleted title master back into the design
        self.master_slide = None
        self.refresh_master_list()
        self.set_master_kind("slide")

    def close_master_view(self) -> None:
        """Save master edits and emit close_requested."""
        if self.master_slide:
            sync_master_slide(self.presentation, self.master_slide)
        self.close_requested.emit()

    def retranslate_ui(self) -> None:
        """Retranslate all Master View components."""
        self.toolbar.retranslate_ui()
        self.lbl_left_title.setText(safe_tr("母版样式"))
        if self.master_list.count() > 0:
            self.master_list.item(0).setText(safe_tr("1. 幻灯片母版"))
        if self.master_list.count() > 1:
            self.master_list.item(1).setText(safe_tr("2. 标题母版"))


_MASTER_TOOLBAR_QSS = """
QToolBar {
    background-color: #F0F0F0;
    border-bottom: 1px solid #C0C0C0;
    padding: 4px;
    spacing: 6px;
}
QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #ABABAB;
    border-radius: 3px;
    padding: 4px 10px;
    font-size: 12px;
    color: #222222;
}
QPushButton:hover {
    background-color: #DCE6F1;
    border: 1px solid #2B579A;
}
QPushButton:checked {
    background-color: #FFEEC2;
    border: 1px solid #2B579A;
    font-weight: bold;
}
QPushButton#btnClose {
    background-color: #2B579A;
    color: #FFFFFF;
    font-weight: bold;
    border: 1px solid #1E3F6F;
}
QPushButton#btnClose:hover {
    background-color: #1E3F6F;
}
"""


def _paint_a4_sheet_and_placeholders(
    painter: QPainter,
    widget_rect: QRectF,
    page_w: float,
    page_h: float,
    master: Any,
) -> tuple[QRectF, float]:
    """Paint A4 paper with drop shadow and header/date/footer/page-number placeholders."""
    painter.fillRect(widget_rect, QColor("#D8DCE3"))

    avail = widget_rect.adjusted(24.0, 20.0, -24.0, -20.0)
    if avail.width() <= 10 or avail.height() <= 10:
        return avail, 1.0

    paper = _fit(avail, page_w / page_h)
    scale = paper.width() / page_w

    # Drop shadow + paper sheet
    painter.fillRect(paper.translated(4.0, 4.0), QColor("#A6ACB8"))
    painter.fillRect(paper, QColor("#FFFFFF"))
    painter.setPen(QPen(QColor("#8E96A4"), 1.0))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(paper)

    def to_px(pt_rect: QRectF) -> QRectF:
        return QRectF(
            paper.x() + pt_rect.x() * scale,
            paper.y() + pt_rect.y() * scale,
            pt_rect.width() * scale,
            pt_rect.height() * scale,
        )

    box_w = (page_w - 2 * MARGIN) * 0.44
    boxes = [
        (
            bool(getattr(master, "show_header", True)),
            getattr(master, "header_text", "") or safe_tr("<页眉>"),
            QRectF(MARGIN, 10.0, box_w, HEADER_H),
            Qt.AlignmentFlag.AlignLeft,
        ),
        (
            bool(getattr(master, "show_date", True)),
            getattr(master, "date_text", "") or safe_tr("<日期/时间>"),
            QRectF(page_w - MARGIN - box_w, 10.0, box_w, HEADER_H),
            Qt.AlignmentFlag.AlignRight,
        ),
        (
            bool(getattr(master, "show_footer", True)),
            getattr(master, "footer_text", "") or safe_tr("<页脚>"),
            QRectF(MARGIN, page_h - FOOTER_H - 8.0, box_w, FOOTER_H),
            Qt.AlignmentFlag.AlignLeft,
        ),
        (
            bool(getattr(master, "show_page_number", True)),
            "<#>",
            QRectF(page_w - MARGIN - box_w, page_h - FOOTER_H - 8.0, box_w, FOOTER_H),
            Qt.AlignmentFlag.AlignRight,
        ),
    ]

    font = ui_font(max(7, int(round(9 * scale))))
    painter.setFont(font)
    for visible, text, pt_rect, align in boxes:
        if not visible:
            continue
        px_rect = to_px(pt_rect)
        painter.setPen(QPen(QColor("#B0B8C4"), 1.0, Qt.PenStyle.DashLine))
        painter.drawRect(px_rect)
        painter.setPen(QColor("#444444"))
        painter.drawText(
            px_rect.adjusted(4.0, 0.0, -4.0, 0.0),
            int(align | Qt.AlignmentFlag.AlignVCenter),
            text,
        )

    return paper, scale


class _PlaceholderControlsMixin:
    """Shared placeholder header/date/footer/page-number control builders."""

    def _init_placeholder_group(self, parent: QWidget, on_change: Any) -> QGroupBox:
        self.grp_placeholders = QGroupBox(safe_tr("页眉和页脚占位符"), parent)
        form = QVBoxLayout(self.grp_placeholders)
        form.setSpacing(6)

        self.chk_header = QCheckBox(safe_tr("页眉"), self.grp_placeholders)
        self.edit_header = QLineEdit(self.grp_placeholders)
        self.edit_header.setPlaceholderText(safe_tr("输入页眉文本..."))

        self.chk_date = QCheckBox(safe_tr("日期和时间"), self.grp_placeholders)
        self.edit_date = QLineEdit(self.grp_placeholders)
        self.edit_date.setPlaceholderText(safe_tr("输入日期文本..."))

        self.chk_footer = QCheckBox(safe_tr("页脚"), self.grp_placeholders)
        self.edit_footer = QLineEdit(self.grp_placeholders)
        self.edit_footer.setPlaceholderText(safe_tr("输入页脚文本..."))

        self.chk_page_number = QCheckBox(safe_tr("页码"), self.grp_placeholders)

        for w in (
            self.chk_header,
            self.edit_header,
            self.chk_date,
            self.edit_date,
            self.chk_footer,
            self.edit_footer,
            self.chk_page_number,
        ):
            form.addWidget(w)

        for chk in (self.chk_header, self.chk_date, self.chk_footer, self.chk_page_number):
            chk.toggled.connect(on_change)
        for edit in (self.edit_header, self.edit_date, self.edit_footer):
            edit.textChanged.connect(on_change)

        return self.grp_placeholders

    def _sync_placeholder_widgets(self, master: Any) -> None:
        widgets = (
            self.chk_header,
            self.edit_header,
            self.chk_date,
            self.edit_date,
            self.chk_footer,
            self.edit_footer,
            self.chk_page_number,
        )
        for w in widgets:
            w.blockSignals(True)
        try:
            self.chk_header.setChecked(bool(master.show_header))
            self.edit_header.setText(master.header_text)
            self.chk_date.setChecked(bool(master.show_date))
            self.edit_date.setText(master.date_text)
            self.chk_footer.setChecked(bool(master.show_footer))
            self.edit_footer.setText(master.footer_text)
            self.chk_page_number.setChecked(bool(master.show_page_number))
        finally:
            for w in widgets:
                w.blockSignals(False)

    def _apply_placeholder_widgets(self, master: Any) -> None:
        master.show_header = self.chk_header.isChecked()
        master.header_text = self.edit_header.text()
        master.show_date = self.chk_date.isChecked()
        master.date_text = self.edit_date.text()
        master.show_footer = self.chk_footer.isChecked()
        master.footer_text = self.edit_footer.text()
        master.show_page_number = self.chk_page_number.isChecked()

    def _retranslate_placeholder_group(self) -> None:
        self.grp_placeholders.setTitle(safe_tr("页眉和页脚占位符"))
        self.chk_header.setText(safe_tr("页眉"))
        self.edit_header.setPlaceholderText(safe_tr("输入页眉文本..."))
        self.chk_date.setText(safe_tr("日期和时间"))
        self.edit_date.setPlaceholderText(safe_tr("输入日期文本..."))
        self.chk_footer.setText(safe_tr("页脚"))
        self.edit_footer.setPlaceholderText(safe_tr("输入页脚文本..."))
        self.chk_page_number.setText(safe_tr("页码"))


class HandoutMasterPreview(QWidget):
    """Interactive WYSIWYG A4 preview for Handout Master layouts and placeholders."""

    def __init__(self, presentation: Presentation, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.presentation = presentation
        self.setMinimumSize(360, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        try:
            hm = self.presentation.handout_master
            page_w, page_h = (A4_PT[1], A4_PT[0]) if hm.orientation == "landscape" else A4_PT
            paper, scale = _paint_a4_sheet_and_placeholders(
                painter, QRectF(self.rect()), page_w, page_h, hm
            )

            aspect = float(self.presentation.w or 960.0) / float(self.presentation.h or 540.0)
            slots = handout_slots(page_w, page_h, hm.slides_per_page, aspect)

            num_font = ui_font(max(8, int(round(12 * scale))), bold=True)
            for idx, slot in enumerate(slots, start=1):
                px_slot = QRectF(
                    paper.x() + slot.x() * scale,
                    paper.y() + slot.y() * scale,
                    slot.width() * scale,
                    slot.height() * scale,
                )
                painter.fillRect(px_slot, QColor("#F5F8FC"))
                painter.setPen(QPen(QColor("#2B579A"), 1.25))
                painter.drawRect(px_slot)

                painter.setFont(num_font)
                painter.setPen(QColor("#2B579A"))
                painter.drawText(px_slot, int(Qt.AlignmentFlag.AlignCenter), str(idx))

                if hm.slides_per_page == 3:
                    x1 = paper.x() + (slot.right() + 20.0) * scale
                    x2 = paper.x() + (page_w - MARGIN) * scale
                    if x2 > x1 + 8.0:
                        painter.setPen(QPen(QColor("#8C95A4"), 1.0))
                        step = px_slot.height() / 6.0
                        for i in range(1, 6):
                            y = px_slot.y() + i * step
                            painter.drawLine(QPointF(x1, y), QPointF(x2, y))
        finally:
            painter.end()


class HandoutMasterView(QWidget, _PlaceholderControlsMixin):
    """Full Handout Master View with 1/2/3/4/6/9 switcher, controls, and A4 preview."""

    close_requested = Signal()
    master_edited = Signal()

    def __init__(
        self,
        presentation: Presentation | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation or Presentation()
        self._syncing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Top Toolbar
        self.toolbar = QToolBar(self)
        self.toolbar.setMovable(False)
        self.toolbar.setStyleSheet(_MASTER_TOOLBAR_QSS)

        self.lbl_title = QLabel(safe_tr("讲义母版视图"), self.toolbar)
        self.lbl_title.setFont(ui_font(9, bold=True))
        self.lbl_title.setStyleSheet("color: #333333; margin-right: 8px;")
        self.toolbar.addWidget(self.lbl_title)

        self.layout_button_group = QButtonGroup(self)
        self.layout_button_group.setExclusive(True)
        self.layout_buttons: dict[int, QPushButton] = {}
        for count in VALID_HANDOUT_COUNTS:
            btn = QPushButton(safe_tr("{0} 张").format(count), self.toolbar)
            btn.setCheckable(True)
            btn.setToolTip(safe_tr("每页 {0} 张幻灯片").format(count))
            btn.clicked.connect(lambda _chk, n=count: self._set_slides_per_page(n))
            self.layout_button_group.addButton(btn, count)
            self.layout_buttons[count] = btn
            self.toolbar.addWidget(btn)

        spacer = QWidget(self.toolbar)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)

        self.btn_close = QPushButton(safe_tr("关闭母版视图"), self.toolbar)
        self.btn_close.setObjectName("btnClose")
        self.btn_close.clicked.connect(self.close_requested.emit)
        self.toolbar.addWidget(self.btn_close)
        root.addWidget(self.toolbar)

        # 2. Splitter: Left Controls + Right A4 Preview
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setHandleWidth(2)

        scroll = QScrollArea(self.splitter)
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(250)
        self.controls_pane = QWidget(scroll)
        ctrl_layout = QVBoxLayout(self.controls_pane)
        ctrl_layout.setContentsMargins(10, 10, 10, 10)
        ctrl_layout.setSpacing(10)

        # Layout & Orientation group
        self.grp_layout = QGroupBox(safe_tr("讲义版式"), self.controls_pane)
        l_form = QFormLayout(self.grp_layout)
        self.lbl_per_page = QLabel(safe_tr("每页幻灯片数:"), self.grp_layout)
        self.combo_per_page = QComboBox(self.grp_layout)
        for count in VALID_HANDOUT_COUNTS:
            self.combo_per_page.addItem(safe_tr("{0} 张幻灯片").format(count), count)
        self.combo_per_page.currentIndexChanged.connect(self._on_per_page_combo_changed)
        l_form.addRow(self.lbl_per_page, self.combo_per_page)

        self.lbl_orientation = QLabel(safe_tr("纸张方向:"), self.grp_layout)
        self.combo_orientation = QComboBox(self.grp_layout)
        self.combo_orientation.addItem(safe_tr("纵向"), "portrait")
        self.combo_orientation.addItem(safe_tr("横向"), "landscape")
        self.combo_orientation.currentIndexChanged.connect(self._on_controls_changed)
        l_form.addRow(self.lbl_orientation, self.combo_orientation)
        ctrl_layout.addWidget(self.grp_layout)

        ctrl_layout.addWidget(
            self._init_placeholder_group(self.controls_pane, self._on_controls_changed)
        )
        ctrl_layout.addStretch()
        scroll.setWidget(self.controls_pane)
        self.splitter.addWidget(scroll)

        self.preview = HandoutMasterPreview(self.presentation, self.splitter)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        root.addWidget(self.splitter)

        self.load_presentation(self.presentation)

    def load_presentation(self, presentation: Presentation) -> None:
        """Load presentation and synchronize widgets from ``handout_master``."""
        self.presentation = presentation
        self.preview.presentation = presentation
        hm = presentation.handout_master
        self._syncing = True
        try:
            self._sync_placeholder_widgets(hm)
            btn = self.layout_buttons.get(hm.slides_per_page)
            if btn is not None:
                btn.setChecked(True)
            idx = self.combo_per_page.findData(hm.slides_per_page)
            if idx >= 0:
                self.combo_per_page.setCurrentIndex(idx)
            oidx = self.combo_orientation.findData(hm.orientation)
            if oidx >= 0:
                self.combo_orientation.setCurrentIndex(oidx)
        finally:
            self._syncing = False
        self.preview.update()

    def _set_slides_per_page(self, count: int) -> None:
        if self._syncing or count not in VALID_HANDOUT_COUNTS:
            return
        self._syncing = True
        try:
            idx = self.combo_per_page.findData(count)
            if idx >= 0:
                self.combo_per_page.setCurrentIndex(idx)
        finally:
            self._syncing = False
        self.presentation.handout_master.slides_per_page = count
        self.preview.update()
        self.master_edited.emit()

    def _on_per_page_combo_changed(self, index: int) -> None:
        if self._syncing:
            return
        count = self.combo_per_page.itemData(index)
        if isinstance(count, int) and count in self.layout_buttons:
            self._syncing = True
            try:
                self.layout_buttons[count].setChecked(True)
            finally:
                self._syncing = False
            self.presentation.handout_master.slides_per_page = count
            self.preview.update()
            self.master_edited.emit()

    def _on_controls_changed(self, *_args: Any) -> None:
        if self._syncing:
            return
        hm = self.presentation.handout_master
        self._apply_placeholder_widgets(hm)
        orient = self.combo_orientation.currentData()
        if orient in ("portrait", "landscape"):
            hm.orientation = orient
        self.preview.update()
        self.master_edited.emit()

    def retranslate_ui(self) -> None:
        self.lbl_title.setText(safe_tr("讲义母版视图"))
        self.btn_close.setText(safe_tr("关闭母版视图"))
        for count, btn in self.layout_buttons.items():
            btn.setText(safe_tr("{0} 张").format(count))
            btn.setToolTip(safe_tr("每页 {0} 张幻灯片").format(count))
        self.grp_layout.setTitle(safe_tr("讲义版式"))
        self.lbl_per_page.setText(safe_tr("每页幻灯片数:"))
        for i, count in enumerate(VALID_HANDOUT_COUNTS):
            self.combo_per_page.setItemText(i, safe_tr("{0} 张幻灯片").format(count))
        self.lbl_orientation.setText(safe_tr("纸张方向:"))
        self.combo_orientation.setItemText(0, safe_tr("纵向"))
        self.combo_orientation.setItemText(1, safe_tr("横向"))
        self._retranslate_placeholder_group()
        self.preview.update()


class NotesMasterPreview(QWidget):
    """Interactive WYSIWYG A4 preview for Notes Master layout, font and borders."""

    def __init__(self, presentation: Presentation, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.presentation = presentation
        self.setMinimumSize(360, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        try:
            nm = self.presentation.notes_master
            page_w, page_h = A4_PT
            paper, scale = _paint_a4_sheet_and_placeholders(
                painter, QRectF(self.rect()), page_w, page_h, nm
            )

            def to_px(pt_rect: QRectF) -> QRectF:
                return QRectF(
                    paper.x() + pt_rect.x() * scale,
                    paper.y() + pt_rect.y() * scale,
                    pt_rect.width() * scale,
                    pt_rect.height() * scale,
                )

            aspect = float(self.presentation.w or 960.0) / float(self.presentation.h or 540.0)
            top = QRectF(
                MARGIN + 36,
                MARGIN + HEADER_H,
                page_w - 2 * MARGIN - 72,
                (page_h - 2 * MARGIN) * 0.42,
            )
            slide_box = to_px(_fit(top, aspect))
            painter.fillRect(slide_box, QColor("#F5F8FC"))
            if nm.show_slide_border:
                painter.setPen(QPen(QColor("#222222"), 1.25))
            else:
                painter.setPen(QPen(QColor("#CBD2DC"), 1.0, Qt.PenStyle.DashLine))
            painter.drawRect(slide_box)
            painter.setFont(ui_font(max(8, int(round(10 * scale))), bold=True))
            painter.setPen(QColor("#2B579A"))
            painter.drawText(slide_box, int(Qt.AlignmentFlag.AlignCenter), safe_tr("幻灯片图像"))

            notes_pt = QRectF(
                MARGIN + 36,
                top.bottom() + 24.0,
                page_w - 2 * MARGIN - 72,
                page_h - top.bottom() - 24.0 - MARGIN - FOOTER_H,
            )
            notes_px = to_px(notes_pt)
            if nm.show_notes_border:
                painter.setPen(QPen(QColor("#222222"), 1.25))
            else:
                painter.setPen(QPen(QColor("#CBD2DC"), 1.0, Qt.PenStyle.DashLine))
            painter.drawRect(notes_px)

            nfont = QFont(nm.notes_font_family or "Arial")
            nfont.setPointSizeF(max(6.0, float(nm.notes_font_size or 12.0) * scale))
            painter.setFont(nfont)
            painter.setPen(QColor("#222222"))
            sample = "\n".join(
                [
                    safe_tr("单击此处编辑母版文本样式"),
                    f"  • {safe_tr('第二级')}",
                    f"    • {safe_tr('第三级')}",
                ]
            )
            painter.drawText(
                notes_px.adjusted(8.0, 8.0, -8.0, -8.0),
                int(
                    Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignTop
                    | Qt.TextFlag.TextWordWrap
                ),
                sample,
            )
        finally:
            painter.end()


class NotesMasterView(QWidget, _PlaceholderControlsMixin):
    """Full Notes Master View with typography, border and placeholder controls."""

    close_requested = Signal()
    master_edited = Signal()

    def __init__(
        self,
        presentation: Presentation | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation or Presentation()
        self._syncing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Top Toolbar
        self.toolbar = QToolBar(self)
        self.toolbar.setMovable(False)
        self.toolbar.setStyleSheet(_MASTER_TOOLBAR_QSS)

        self.lbl_title = QLabel(safe_tr("备注母版视图"), self.toolbar)
        self.lbl_title.setFont(ui_font(9, bold=True))
        self.lbl_title.setStyleSheet("color: #333333; margin-right: 12px;")
        self.toolbar.addWidget(self.lbl_title)

        spacer = QWidget(self.toolbar)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)

        self.btn_close = QPushButton(safe_tr("关闭母版视图"), self.toolbar)
        self.btn_close.setObjectName("btnClose")
        self.btn_close.clicked.connect(self.close_requested.emit)
        self.toolbar.addWidget(self.btn_close)
        root.addWidget(self.toolbar)

        # 2. Splitter: Left Controls + Right A4 Preview
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setHandleWidth(2)

        scroll = QScrollArea(self.splitter)
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(250)
        self.controls_pane = QWidget(scroll)
        ctrl_layout = QVBoxLayout(self.controls_pane)
        ctrl_layout.setContentsMargins(10, 10, 10, 10)
        ctrl_layout.setSpacing(10)

        # Typography & Border group
        self.grp_notes_style = QGroupBox(safe_tr("备注正文与边框"), self.controls_pane)
        s_form = QFormLayout(self.grp_notes_style)

        self.lbl_font_family = QLabel(safe_tr("备注字体:"), self.grp_notes_style)
        self.font_combo = QComboBox(self.grp_notes_style)
        self.font_combo.setEditable(True)
        self.font_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        preset_fonts = [
            "Arial",
            "Times New Roman",
            "Georgia",
            "Courier New",
            "Verdana",
            "Tahoma",
            "SimSun",
            "Microsoft YaHei",
        ]
        seen = set(preset_fonts)
        families = list(preset_fonts) + [f for f in QFontDatabase.families() if f not in seen]
        self.font_combo.addItems(families)
        self.font_combo.currentTextChanged.connect(self._on_controls_changed)
        s_form.addRow(self.lbl_font_family, self.font_combo)

        self.lbl_font_size = QLabel(safe_tr("备注字号:"), self.grp_notes_style)
        self.font_size_spin = QDoubleSpinBox(self.grp_notes_style)
        self.font_size_spin.setRange(6.0, 72.0)
        self.font_size_spin.setDecimals(1)
        self.font_size_spin.setSingleStep(1.0)
        self.font_size_spin.valueChanged.connect(self._on_controls_changed)
        s_form.addRow(self.lbl_font_size, self.font_size_spin)

        self.chk_slide_border = QCheckBox(safe_tr("显示幻灯片边框"), self.grp_notes_style)
        self.chk_slide_border.toggled.connect(self._on_controls_changed)
        s_form.addRow(self.chk_slide_border)

        self.chk_notes_border = QCheckBox(safe_tr("显示备注区边框"), self.grp_notes_style)
        self.chk_notes_border.toggled.connect(self._on_controls_changed)
        s_form.addRow(self.chk_notes_border)

        ctrl_layout.addWidget(self.grp_notes_style)
        ctrl_layout.addWidget(
            self._init_placeholder_group(self.controls_pane, self._on_controls_changed)
        )
        ctrl_layout.addStretch()
        scroll.setWidget(self.controls_pane)
        self.splitter.addWidget(scroll)

        self.preview = NotesMasterPreview(self.presentation, self.splitter)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        root.addWidget(self.splitter)

        self.load_presentation(self.presentation)

    def load_presentation(self, presentation: Presentation) -> None:
        """Load presentation and synchronize widgets from ``notes_master``."""
        self.presentation = presentation
        self.preview.presentation = presentation
        nm = presentation.notes_master
        self._syncing = True
        try:
            self._sync_placeholder_widgets(nm)
            self.font_combo.setCurrentText(nm.notes_font_family or "Arial")
            self.font_size_spin.setValue(float(nm.notes_font_size or 12.0))
            self.chk_slide_border.setChecked(bool(nm.show_slide_border))
            self.chk_notes_border.setChecked(bool(nm.show_notes_border))
        finally:
            self._syncing = False
        self.preview.update()

    def _on_controls_changed(self, *_args: Any) -> None:
        if self._syncing:
            return
        nm = self.presentation.notes_master
        self._apply_placeholder_widgets(nm)
        nm.notes_font_family = self.font_combo.currentText().strip() or "Arial"
        nm.notes_font_size = float(self.font_size_spin.value())
        nm.show_slide_border = self.chk_slide_border.isChecked()
        nm.show_notes_border = self.chk_notes_border.isChecked()
        self.preview.update()
        self.master_edited.emit()

    def retranslate_ui(self) -> None:
        self.lbl_title.setText(safe_tr("备注母版视图"))
        self.btn_close.setText(safe_tr("关闭母版视图"))
        self.grp_notes_style.setTitle(safe_tr("备注正文与边框"))
        self.lbl_font_family.setText(safe_tr("备注字体:"))
        self.lbl_font_size.setText(safe_tr("备注字号:"))
        self.chk_slide_border.setText(safe_tr("显示幻灯片边框"))
        self.chk_notes_border.setText(safe_tr("显示备注区边框"))
        self._retranslate_placeholder_group()
        self.preview.update()
