"""Office 2003 classic appearance theme selector dialog with live preview."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import get_i18n_manager, safe_tr
from atboffice.core.settings import get_app_settings
from atboffice.ui.styles.luna_2003 import (
    CLASSIC_DOCK_TOP,
    CLASSIC_HOT_BORDER,
    CLASSIC_TB_A,
    CLASSIC_TB_B,
    CLASSIC_TB_C,
    LUNA_BLUE_DOCK_TOP,
    LUNA_BLUE_HOT_BORDER,
    LUNA_BLUE_TB_A,
    LUNA_BLUE_TB_B,
    LUNA_BLUE_TB_C,
    LUNA_OLIVE_DOCK_TOP,
    LUNA_OLIVE_HOT_BORDER,
    LUNA_OLIVE_TB_A,
    LUNA_OLIVE_TB_B,
    LUNA_OLIVE_TB_C,
    LUNA_SILVER_DOCK_TOP,
    LUNA_SILVER_HOT_BORDER,
    LUNA_SILVER_TB_A,
    LUNA_SILVER_TB_B,
    LUNA_SILVER_TB_C,
    THEMES,
    apply_theme_globally,
)

if TYPE_CHECKING:
    pass


class ThemePreviewCanvas(QWidget):
    """Miniature visual drawing representing the window dock and command bar."""

    def __init__(self, theme_key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme_key = theme_key
        self.setFixedHeight(54)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w = self.width()
        h = self.height()

        if self.theme_key == "silver":
            dock = QColor(LUNA_SILVER_DOCK_TOP)
            tb_a = QColor(LUNA_SILVER_TB_A)
            tb_b = QColor(LUNA_SILVER_TB_B)
            tb_c = QColor(LUNA_SILVER_TB_C)
            border = QColor(LUNA_SILVER_HOT_BORDER)
        elif self.theme_key == "olive":
            dock = QColor(LUNA_OLIVE_DOCK_TOP)
            tb_a = QColor(LUNA_OLIVE_TB_A)
            tb_b = QColor(LUNA_OLIVE_TB_B)
            tb_c = QColor(LUNA_OLIVE_TB_C)
            border = QColor(LUNA_OLIVE_HOT_BORDER)
        elif self.theme_key == "classic":
            dock = QColor(CLASSIC_DOCK_TOP)
            tb_a = QColor(CLASSIC_TB_A)
            tb_b = QColor(CLASSIC_TB_B)
            tb_c = QColor(CLASSIC_TB_C)
            border = QColor(CLASSIC_HOT_BORDER)
        else:
            dock = QColor(LUNA_BLUE_DOCK_TOP)
            tb_a = QColor(LUNA_BLUE_TB_A)
            tb_b = QColor(LUNA_BLUE_TB_B)
            tb_c = QColor(LUNA_BLUE_TB_C)
            border = QColor(LUNA_BLUE_HOT_BORDER)

        # Draw dock background
        painter.fillRect(0, 0, w, h, dock)

        # Draw simulated command toolbar
        tb_rect_h = 24
        painter.fillRect(6, 6, w - 12, tb_rect_h, tb_a)
        painter.fillRect(6, 6 + 8, w - 12, tb_rect_h - 8, tb_b)
        painter.fillRect(6, 6 + 16, w - 12, tb_rect_h - 16, tb_c)
        painter.setPen(border)
        painter.drawRect(6, 6, w - 12, tb_rect_h)

        # Draw miniature tool buttons inside toolbar
        btn_w = 18
        for i in range(4):
            bx = 12 + i * (btn_w + 4)
            painter.fillRect(bx, 9, btn_w, 18, QColor(255, 255, 255, 120))
            painter.drawRect(bx, 9, btn_w, 18)


class ThemeCard(QFrame):
    """Clickable interactive card component showcasing a single theme."""

    clicked = Signal(str)

    def __init__(
        self,
        theme_key: str,
        title: str,
        description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.theme_key = theme_key
        self.title_text = title
        self.desc_text = description
        self.is_selected = False

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Preview Swatch
        self.preview = ThemePreviewCanvas(theme_key, self)
        layout.addWidget(self.preview)

        # Title & Checkmark Header
        hdr = QHBoxLayout()
        hdr.setSpacing(4)
        self.lbl_title = QLabel(title, self)
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        self.lbl_title.setFont(title_font)
        hdr.addWidget(self.lbl_title)

        hdr.addStretch(1)
        self.lbl_badge = QLabel("", self)
        hdr.addWidget(self.lbl_badge)
        layout.addLayout(hdr)

        # Description
        self.lbl_desc = QLabel(description, self)
        self.lbl_desc.setWordWrap(True)
        desc_font = QFont()
        desc_font.setPointSize(9)
        self.lbl_desc.setFont(desc_font)
        self.lbl_desc.setStyleSheet("color: #64748B;")
        layout.addWidget(self.lbl_desc)

        self._update_style()

    def set_selected(self, selected: bool) -> None:
        """Update active selection state and redraw borders."""
        self.is_selected = selected
        self._update_style()

    def _update_style(self) -> None:
        if self.is_selected:
            self.setStyleSheet(
                "ThemeCard { background: #F0F7FF; border: 2px solid #0284C7; "
                "border-radius: 6px; }"
            )
            self.lbl_badge.setText("✓ " + safe_tr("当前"))
            self.lbl_badge.setStyleSheet(
                "color: #0284C7; font-weight: bold; font-size: 10px;"
            )
        else:
            self.setStyleSheet(
                "ThemeCard { background: #FFFFFF; border: 1px solid #CBD5E1; "
                "border-radius: 6px; }"
                "ThemeCard:hover { border: 1px solid #38BDF8; background: #F8FAFC; }"
            )
            self.lbl_badge.setText("")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Emit clicked signal when user clicks anywhere on the card."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.theme_key)
        super().mousePressEvent(event)


class ThemeDialog(QDialog):
    """Full-featured Office 2003 Theme Selector with immediate live preview."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = get_app_settings()
        self.initial_theme = str(self.settings.get_value("theme/active_theme", "blue"))
        self.selected_theme = self.initial_theme
        self.live_preview = True

        self.cards: dict[str, ThemeCard] = {}
        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        self.resize(520, 390)
        self.setMinimumSize(460, 340)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # Header description
        self.lbl_header = QLabel(
            safe_tr("选择您喜欢的 Office 2003 经典视觉主题，点击卡片可即时预览效果。"),
            self,
        )
        self.lbl_header.setWordWrap(True)
        root.addWidget(self.lbl_header)

        # 2x2 Grid of Theme Cards
        grid = QGridLayout()
        grid.setSpacing(12)

        coords = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for idx, (t_key, t_title, t_desc) in enumerate(THEMES):
            r, c = coords[idx]
            card = ThemeCard(t_key, safe_tr(t_title), safe_tr(t_desc), self)
            card.clicked.connect(self._on_card_selected)
            if t_key == self.selected_theme:
                card.set_selected(True)
            self.cards[t_key] = card
            grid.addWidget(card, r, c)

        root.addLayout(grid)

        # Live preview checkbox
        self.chk_live_preview = QCheckBox(safe_tr("即时预览主题效果"), self)
        self.chk_live_preview.setChecked(True)
        self.chk_live_preview.toggled.connect(self._on_live_preview_toggled)
        root.addWidget(self.chk_live_preview)

        # Button Box
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self._on_reject)
        root.addWidget(self.button_box)

    def _on_live_preview_toggled(self, checked: bool) -> None:
        self.live_preview = checked
        if checked:
            apply_theme_globally(self.selected_theme)
        else:
            apply_theme_globally(self.initial_theme)

    def _on_card_selected(self, theme_key: str) -> None:
        self.selected_theme = theme_key
        for k, card in self.cards.items():
            card.set_selected(k == theme_key)

        if self.live_preview:
            apply_theme_globally(theme_key)

    def _on_accept(self) -> None:
        self.settings.set_value("theme/active_theme", self.selected_theme)
        apply_theme_globally(self.selected_theme)
        self.accept()

    def _on_reject(self) -> None:
        if self.selected_theme != self.initial_theme:
            apply_theme_globally(self.initial_theme)
        self.reject()

    def retranslate_ui(self) -> None:
        """Update localized UI text dynamically."""
        if get_i18n_manager().current_locale == "en":
            self.setWindowTitle("Themes")
        else:
            self.setWindowTitle(safe_tr("外观主题选择器"))
        self.lbl_header.setText(
            safe_tr("选择您喜欢的 Office 2003 经典视觉主题，点击卡片可即时预览效果。")
        )
        self.chk_live_preview.setText(safe_tr("即时预览主题效果"))
        for t_key, t_title, t_desc in THEMES:
            if t_key in self.cards:
                self.cards[t_key].lbl_title.setText(safe_tr(t_title))
                self.cards[t_key].lbl_desc.setText(safe_tr(t_desc))
                self.cards[t_key]._update_style()
