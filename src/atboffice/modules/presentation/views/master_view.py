"""Slide Master View (幻灯片母版视图) for Lectern presentations.

Provides:
- Authentic PowerPoint 2003 Slide Master editing environment.
- Dedicated master close toolbar with "Close Master View", "Insert Title Master", and "Delete Title Master".
- Left-hand master hierarchy list (Slide Master / Title Master).
- Full WYSIWYG master canvas showing title, multi-level body, and footer placeholders.
- Seamless synchronization with presentation DesignTemplate on close.
- 100% i18n support with safe_tr and retranslate_ui.
"""

from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.designs import DesignTemplate
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.views.slide_canvas import (
    SlideCanvasView,
    SlideScene,
)
from atboffice.modules.presentation.views.workspace import (
    build_master_slide,
    render_slide_thumbnail,
    sync_master_slide,
)


def safe_tr(text: str) -> str:
    """Safe translation for Slide Master UI."""
    app = QApplication.instance()
    if app:
        translated = app.translate("SlideMaster", text)
        if translated and translated != text:
            return translated
    return text


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
        self.lbl_title.setFont(QFont("Arial", 9, QFont.Weight.Bold))
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
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation or Presentation()
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
        self.lbl_left_title.setFont(QFont("Arial", 9, QFont.Weight.Bold))
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

        self.scene = SlideScene(parent=self)
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
        self.refresh_master_list()
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
        has_title_master = (
            design.title_decorations is not None or design.title_bg is not None
        )
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
