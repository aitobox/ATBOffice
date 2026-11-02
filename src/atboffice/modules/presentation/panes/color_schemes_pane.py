"""PowerPoint 2003 Slide Design - Color Schemes Task Pane for Lectern."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.designs import DESIGNS, ColorScheme

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.presentation import Presentation


def safe_tr(text: str) -> str:
    """Translate UI text safely for ColorSchemesPane."""
    return QCoreApplication.translate("ColorSchemesPane", text)


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


class ColorSchemeCard(QToolButton):
    """Visual card displaying 8-color palette swatches."""

    apply_requested = Signal(bool)  # apply_to_all

    def __init__(
        self,
        scheme: ColorScheme,
        name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.scheme = scheme
        self.scheme_name = name
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.setStyleSheet(
            """
            QToolButton {
                background-color: #FFFFFF;
                border: 1px solid #D0D0D0;
                border-radius: 2px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: #E5EEF8;
                border: 1px solid #2B579A;
            }
            """
        )

        menu = QMenu(self)
        act_all = menu.addAction(safe_tr("应用到所有幻灯片(&A)"))
        act_sel = menu.addAction(safe_tr("应用到所选幻灯片(&S)"))
        act_all.triggered.connect(lambda: self.apply_requested.emit(True))
        act_sel.triggered.connect(lambda: self.apply_requested.emit(False))
        self.setMenu(menu)

        self.clicked.connect(lambda: self.apply_requested.emit(True))
        self._update_icon()

    def _update_icon(self) -> None:
        pix = QPixmap(104, 32)
        pix.fill(QColor("#FFFFFF"))
        painter = QPainter(pix)
        try:
            colors = [
                self.scheme.lt1,
                self.scheme.dk1,
                self.scheme.lt2,
                self.scheme.dk2,
                self.scheme.accent1,
                self.scheme.accent2,
                self.scheme.hlink,
                self.scheme.folHlink,
            ]
            w = 12
            h = 24
            for i, c in enumerate(colors):
                x = 4 + i * 12
                painter.fillRect(QRectF(x, 4, w, h), QColor(c))
                painter.setPen(QColor("#7B9EBD"))
                painter.drawRect(QRectF(x, 4, w - 1, h - 1))
        finally:
            painter.end()
        self.setIcon(pix)
        self.setIconSize(QSize(104, 32))


class ColorSchemesPane(QWidget):
    """Slide Design - Color Schemes task pane."""

    apply_color_scheme_requested = Signal(ColorScheme, bool)  # (scheme, apply_to_all)
    navigate_pane = Signal(str)
    edit_color_scheme_requested = Signal()

    def __init__(
        self,
        presentation: Presentation | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation
        self.scheme_cards: list[ColorSchemeCard] = []
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

        # Divider
        div = QFrame(self)
        div.setFrameShape(QFrame.Shape.HLine)
        div.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(div)

        # 2. Section label
        self.lbl_apply = QLabel(safe_tr("应用配色方案:"), self)
        self.lbl_apply.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        main_layout.addWidget(self.lbl_apply)

        # 3. Scrollable schemes grid
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget()
        self.grid_layout = QVBoxLayout(self.container)
        self.grid_layout.setContentsMargins(2, 2, 2, 2)
        self.grid_layout.setSpacing(6)

        self._populate_schemes()

        self.grid_layout.addStretch()
        scroll.setWidget(self.container)
        main_layout.addWidget(scroll, 1)

        # 4. Edit Color Schemes link button
        self.btn_edit = PaneLinkButton(safe_tr("编辑配色方案..."), self)
        self.btn_edit.clicked.connect(self.edit_color_scheme_requested.emit)
        main_layout.addWidget(self.btn_edit)

    def _populate_schemes(self) -> None:
        self.scheme_cards.clear()
        # Collect unique schemes from DESIGNS
        schemes: list[ColorScheme] = []
        for d in DESIGNS:
            if d.colors and d.colors not in schemes:
                schemes.append(d.colors)

        for i, s in enumerate(schemes):
            card = ColorSchemeCard(s, name=f"Scheme {i + 1}", parent=self)
            card.apply_requested.connect(
                lambda apply_all, sc=s: self.apply_color_scheme_requested.emit(sc, apply_all)
            )
            self.scheme_cards.append(card)
            self.grid_layout.addWidget(card)

    def retranslate_ui(self) -> None:
        """Retranslate UI texts upon language change."""
        self.btn_nav_design.setText(safe_tr("设计模板"))
        self.btn_nav_colors.setText(safe_tr("配色方案"))
        self.btn_nav_anims.setText(safe_tr("动画方案"))
        self.lbl_apply.setText(safe_tr("应用配色方案:"))
        self.btn_edit.setText(safe_tr("编辑配色方案..."))
