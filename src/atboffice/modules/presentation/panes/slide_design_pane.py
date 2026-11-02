"""PowerPoint 2003 Slide Design - Design Templates Task Pane for Lectern."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.designs import DESIGNS, DesignDefinition, build_design

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.presentation import Presentation


def safe_tr(text: str) -> str:
    """Translate UI text safely for SlideDesignPane."""
    return QCoreApplication.translate("SlideDesignPane", text)


class PaneLinkButton(QPushButton):
    """Hyperlink button for top task pane navigation."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet(
            """
            QPushButton {
                color: #000080;
                text-decoration: underline;
                text-align: left;
                background: transparent;
                border: none;
                font-size: 11px;
                padding: 2px 4px;
            }
            QPushButton:hover {
                color: #FF0000;
            }
            """
        )


class SlideDesignPane(QWidget):
    """Slide Design task pane (Design Templates gallery)."""

    apply_design_requested = Signal(str, bool)  # (design_key, apply_to_all)
    navigate_pane = Signal(str)  # 'design', 'colors', 'animations'
    browse_design_requested = Signal()

    def __init__(
        self,
        presentation: Presentation | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation
        self.design_cards: dict[str, QToolButton] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # 1. Top navigation switcher links
        self.nav_box = QWidget(self)
        nav_layout = QVBoxLayout(self.nav_box)
        nav_layout.setContentsMargins(0, 0, 0, 4)
        nav_layout.setSpacing(2)

        self.btn_nav_design = PaneLinkButton(safe_tr("设计模板"), self)
        self.btn_nav_colors = PaneLinkButton(safe_tr("配色方案"), self)
        self.btn_nav_anims = PaneLinkButton(safe_tr("动画方案"), self)

        self.btn_nav_design.clicked.connect(lambda: self.navigate_pane.emit("design"))
        self.btn_nav_colors.clicked.connect(lambda: self.navigate_pane.emit("colors"))
        self.btn_nav_anims.clicked.connect(lambda: self.navigate_pane.emit("animations"))

        nav_layout.addWidget(self.btn_nav_design)
        nav_layout.addWidget(self.btn_nav_colors)
        nav_layout.addWidget(self.btn_nav_anims)
        main_layout.addWidget(self.nav_box)

        # Divider line
        div = QFrame(self)
        div.setFrameShape(QFrame.Shape.HLine)
        div.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(div)

        # 2. Scroll Area containing template galleries
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget()
        self.content_layout = QVBoxLayout(self.container)
        self.content_layout.setContentsMargins(2, 2, 2, 2)
        self.content_layout.setSpacing(8)

        # Used in this presentation section
        self.lbl_used = QLabel(safe_tr("在此演示文稿中使用:"), self)
        self.lbl_used.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.content_layout.addWidget(self.lbl_used)

        self.used_container = QWidget(self)
        self.used_layout = QVBoxLayout(self.used_container)
        self.used_layout.setContentsMargins(0, 0, 0, 0)
        self.used_layout.setSpacing(4)
        self.content_layout.addWidget(self.used_container)

        # Available for use section
        self.lbl_available = QLabel(safe_tr("可供使用:"), self)
        self.lbl_available.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.content_layout.addWidget(self.lbl_available)

        self.avail_container = QWidget(self)
        self.avail_layout = QVBoxLayout(self.avail_container)
        self.avail_layout.setContentsMargins(0, 0, 0, 0)
        self.avail_layout.setSpacing(4)
        self.content_layout.addWidget(self.avail_container)

        self._populate_designs()

        self.content_layout.addStretch()

        # 3. Browse button
        self.btn_browse = QPushButton(safe_tr("浏览..."), self)
        self.btn_browse.setStyleSheet("text-align: center; padding: 4px;")
        self.btn_browse.clicked.connect(self.browse_design_requested.emit)
        self.content_layout.addWidget(self.btn_browse)

        scroll.setWidget(self.container)
        main_layout.addWidget(scroll, 1)

    def _create_thumbnail_icon(self, defn: DesignDefinition) -> QIcon:
        pix = QPixmap(56, 42)
        pix.fill(QColor(defn.colors.lt1))
        painter = QPainter(pix)
        try:
            # Title bar strip
            painter.fillRect(QRectF(0, 0, 56, 12), QColor(defn.colors.accent1))
            # Body lines simulation
            painter.fillRect(QRectF(6, 16, 26, 4), QColor(defn.colors.dk1))
            painter.fillRect(QRectF(6, 24, 44, 3), QColor(defn.colors.accent2))
            painter.fillRect(QRectF(6, 30, 36, 3), QColor(defn.colors.lt2))
            # Border
            painter.setPen(QColor("#7B9EBD"))
            painter.drawRect(0, 0, 55, 41)
        finally:
            painter.end()
        return QIcon(pix)

    def _populate_designs(self) -> None:
        # Clear existing
        self.design_cards.clear()

        # Build available designs
        for defn in DESIGNS:
            card = self._create_card_button(defn)
            self.design_cards[defn.key] = card
            self.avail_layout.addWidget(card)

        self.refresh_used_designs()

    def _create_card_button(self, defn: DesignDefinition) -> QToolButton:
        btn = QToolButton(self)
        btn.setText(safe_tr(defn.name))
        btn.setIcon(self._create_thumbnail_icon(defn))
        btn.setIconSize(QSize(56, 42))
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        btn.setStyleSheet(
            """
            QToolButton {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 2px;
                padding: 4px;
                font-size: 11px;
                text-align: left;
            }
            QToolButton:hover {
                background-color: #E5EEF8;
                border: 1px solid #2B579A;
            }
            """
        )

        menu = QMenu(btn)
        act_all = menu.addAction(safe_tr("应用到所有幻灯片(&A)"))
        act_sel = menu.addAction(safe_tr("应用到所选幻灯片(&S)"))
        act_all.triggered.connect(lambda: self.apply_design_requested.emit(defn.key, True))
        act_sel.triggered.connect(lambda: self.apply_design_requested.emit(defn.key, False))
        btn.setMenu(menu)

        btn.clicked.connect(lambda: self.apply_design_requested.emit(defn.key, True))
        return btn

    def refresh_used_designs(self) -> None:
        """Refresh designs listed under 'Used in this presentation'."""
        while self.used_layout.count():
            item = self.used_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        used_keys: set[str] = set()
        if self.presentation and self.presentation.slides:
            for s in self.presentation.slides:
                did = getattr(s, "design_id", None) or getattr(s, "design", None)
                if did:
                    used_keys.add(did)

        if not used_keys:
            used_keys.add("default")

        for key in sorted(used_keys):
            defn = next((d for d in DESIGNS if d.key == key), None)
            if defn:
                card = self._create_card_button(defn)
                self.used_layout.addWidget(card)

    def retranslate_ui(self) -> None:
        """Retranslate UI texts upon language change."""
        self.btn_nav_design.setText(safe_tr("设计模板"))
        self.btn_nav_colors.setText(safe_tr("配色方案"))
        self.btn_nav_anims.setText(safe_tr("动画方案"))
        self.lbl_used.setText(safe_tr("在此演示文稿中使用:"))
        self.lbl_available.setText(safe_tr("可供使用:"))
        self.btn_browse.setText(safe_tr("浏览..."))
        for k, btn in self.design_cards.items():
            defn = next((d for d in DESIGNS if d.key == k), None)
            if defn:
                btn.setText(safe_tr(defn.name))
