"""PowerPoint 2003 Slide Layout Task Pane for Lectern."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.designs import build_design
from atboffice.modules.presentation.models.layouts import (
    LAYOUTS,
    LayoutInfo,
    layout_frames,
)

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.presentation import Presentation


def safe_tr(text: str) -> str:
    """Translate UI text safely for SlideLayoutPane."""
    return QCoreApplication.translate("SlideLayoutPane", text)


class LayoutCardButton(QToolButton):
    """Layout thumbnail button with right-click context menu."""

    apply_layout_requested = Signal(str)
    reapply_master_requested = Signal(str)
    insert_slide_requested = Signal(str)

    def __init__(self, layout_info: LayoutInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.layout_info = layout_info
        self.setText(safe_tr(layout_info.name))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(64, 48))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            """
            QToolButton {
                background-color: #FFFFFF;
                border: 1px solid #C0C0C0;
                border-radius: 2px;
                padding: 4px;
                font-size: 10px;
                text-align: center;
            }
            QToolButton:hover {
                background-color: #E5EEF8;
                border: 1px solid #2B579A;
            }
            QToolButton:checked {
                background-color: #B6BDD2;
                border: 1px solid #0A246A;
            }
            """
        )
        self.setCheckable(True)
        self.clicked.connect(lambda: self.apply_layout_requested.emit(self.layout_info.key))

    def contextMenuEvent(self, event: Any) -> None:
        menu = QMenu(self)
        act_apply = menu.addAction(safe_tr("应用于选定幻灯片(&S)"))
        act_apply.triggered.connect(lambda: self.apply_layout_requested.emit(self.layout_info.key))

        act_reapply = menu.addAction(safe_tr("重新应用母版样式(&R)"))
        act_reapply.triggered.connect(
            lambda: self.reapply_master_requested.emit(self.layout_info.key)
        )

        menu.addSeparator()
        act_insert = menu.addAction(safe_tr("插入新幻灯片(&I)"))
        act_insert.triggered.connect(lambda: self.insert_slide_requested.emit(self.layout_info.key))

        menu.exec(event.globalPos())


class SlideLayoutPane(QWidget):
    """Slide Layout task pane (PowerPoint 2003 21 standard layouts)."""

    layout_applied = Signal(str)
    reapply_master_requested = Signal(str)
    insert_slide_requested = Signal(str)

    def __init__(
        self,
        presentation: Presentation | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation
        self.layout_cards: dict[str, LayoutCardButton] = {}
        self._cached_design = build_design("default", 64.0, 48.0)
        self._current_layout_key: str | None = None

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Top prompt label
        self.lbl_prompt = QLabel(safe_tr("应用幻灯片版式:"), self)
        self.lbl_prompt.setStyleSheet("color: #333333; font-weight: bold; margin-bottom: 2px;")
        main_layout.addWidget(self.lbl_prompt)

        # Scrollable gallery
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Group layouts
        groups: dict[str, list[LayoutInfo]] = {}
        for layout_info in LAYOUTS:
            groups.setdefault(layout_info.group, []).append(layout_info)

        self.group_names = {
            "Text Layouts": safe_tr("文本版式:"),
            "Content Layouts": safe_tr("内容版式:"),
            "Text and Content Layouts": safe_tr("文本与内容版式:"),
            "Other Layouts": safe_tr("其他版式:"),
        }
        self.group_labels: dict[str, QLabel] = {}

        for grp_key, grp_layouts in groups.items():
            lbl = QLabel(self.group_names.get(grp_key, grp_key), self)
            lbl.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            lbl.setStyleSheet("color: #000080; margin-top: 4px; font-weight: bold;")
            layout.addWidget(lbl)
            self.group_labels[grp_key] = lbl

            for layout_item in grp_layouts:
                btn = LayoutCardButton(layout_item, self)
                btn.setIcon(self._create_layout_icon(layout_item.key))
                btn.apply_layout_requested.connect(self.apply_layout)
                btn.reapply_master_requested.connect(self.reapply_master_requested.emit)
                btn.insert_slide_requested.connect(self.insert_slide_requested.emit)
                self.layout_cards[layout_item.key] = btn
                layout.addWidget(btn)

        layout.addStretch()
        self.scroll.setWidget(container)
        main_layout.addWidget(self.scroll, stretch=1)

        # Bottom option: Show when inserting new slides
        self.chk_show_on_new = QCheckBox(safe_tr("插入新幻灯片时显示(&S)"), self)
        self.chk_show_on_new.setChecked(True)
        main_layout.addWidget(self.chk_show_on_new)

    def _create_layout_icon(self, key: str) -> QIcon:
        """Create SVG/vector thumbnail icon representing the layout geometry."""
        pix = QPixmap(64, 48)
        pix.fill(QColor("#FFFFFF"))
        painter = QPainter(pix)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QPen(QColor("#B0B0B0"), 1.0))
            painter.drawRect(0, 0, 63, 47)

            frames = layout_frames(key, self._cached_design)
            for f in frames:
                fx = float(f.get("x", 0))
                fy = float(f.get("y", 0))
                fw = float(f.get("w", 20))
                fh = float(f.get("h", 10))
                ftype = f.get("type", "")
                if ftype in ("title", "ctrTitle"):
                    painter.fillRect(QRectF(fx, fy, fw, fh), QColor("#7A7A7A"))
                elif ftype == "subTitle":
                    painter.fillRect(QRectF(fx, fy, fw, fh), QColor("#A8A8A8"))
                elif ftype == "body":
                    painter.fillRect(QRectF(fx, fy, fw, fh), QColor("#A8A8A8"))
                elif ftype == "tbl":
                    painter.fillRect(QRectF(fx, fy, fw, fh), QColor("#EAF0F8"))
                    painter.setPen(QPen(QColor("#3A5A8C"), 1.0))
                    painter.drawRect(QRectF(fx, fy, fw, fh))
                elif ftype == "chart":
                    painter.fillRect(QRectF(fx, fy, fw, fh), QColor("#F8F0E8"))
                    painter.setPen(QPen(QColor("#993366"), 1.0))
                    painter.drawRect(QRectF(fx, fy, fw, fh))
                else:
                    painter.setPen(QPen(QColor("#2B579A"), 1.0, Qt.PenStyle.DashLine))
                    painter.drawRect(QRectF(fx, fy, fw, fh))
        finally:
            painter.end()
        return QIcon(pix)

    def set_active_layout(self, layout_key: str | None) -> None:
        """Update active layout highlight in gallery."""
        self._current_layout_key = layout_key
        for k, btn in self.layout_cards.items():
            btn.setChecked(k == layout_key)

    def apply_layout(self, key: str) -> None:
        """Emit layout selection signal."""
        self.set_active_layout(key)
        self.layout_applied.emit(key)

    def retranslate_ui(self) -> None:
        """Update localized UI text."""
        self.lbl_prompt.setText(safe_tr("应用幻灯片版式:"))
        self.chk_show_on_new.setText(safe_tr("插入新幻灯片时显示(&S)"))
        for grp_key, lbl in self.group_labels.items():
            lbl.setText(self.group_names.get(grp_key, grp_key))
        for key, btn in self.layout_cards.items():
            btn.setText(safe_tr(btn.layout_info.name))
