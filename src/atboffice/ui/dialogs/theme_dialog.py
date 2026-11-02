"""Office 2003 classic appearance theme selector dialog with live preview."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

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
    QPushButton,
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
    """Full-featured Office 2003 / Suite Theme Selector with immediate live preview."""

    def __init__(self, parent: QWidget | None = None, mode: str = "luna") -> None:
        super().__init__(parent)
        self.mode = mode
        self.settings = get_app_settings()
        self.initial_theme = str(self.settings.get_value("theme/active_theme", "blue"))
        self.selected_theme = self.initial_theme
        self.live_preview = True

        self.cards: dict[str, Any] = {}
        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        if self.mode == "suite":
            self.resize(640, 320)
            self.setMinimumSize(560, 280)
            root = QVBoxLayout(self)
            root.setContentsMargins(20, 18, 20, 18)
            root.setSpacing(14)

            self.lbl_header = QLabel(
                safe_tr("选择 ATBOffice 的整体外观风格。所有打开的窗口将同步即时生效。"),
                self,
            )
            self.lbl_header.setWordWrap(True)
            self.lbl_header.setStyleSheet("font-size: 13px; color: #334155;")
            root.addWidget(self.lbl_header)

            cards_layout = QHBoxLayout()
            cards_layout.setSpacing(12)

            for t_key, t_title, t_desc, layout_type in SUITE_THEMES:
                card = SuiteThemeCard(
                    t_key, safe_tr(t_title), safe_tr(t_desc), layout_type, self
                )
                card.clicked.connect(self._on_card_selected)
                if t_key == self.selected_theme:
                    card.set_selected(True)
                self.cards[t_key] = card
                cards_layout.addWidget(card)

            root.addLayout(cards_layout)

            # Live preview checkbox
            self.chk_live_preview = QCheckBox(safe_tr("即时预览主题效果"), self)
            self.chk_live_preview.setChecked(True)
            self.chk_live_preview.toggled.connect(self._on_live_preview_toggled)
            root.addWidget(self.chk_live_preview)

            self.button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
                self,
            )
            self.button_box.accepted.connect(self._on_accept)
            self.button_box.rejected.connect(self._on_reject)
            root.addWidget(self.button_box)
            return

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
        if self.mode == "suite":
            self.setWindowTitle(safe_tr("主题 — ATBOffice"))
            self.lbl_header.setText(
                safe_tr("选择 ATBOffice 的整体外观风格。所有打开的窗口将同步即时生效。")
            )
            self.chk_live_preview.setText(safe_tr("即时预览主题效果"))
            for t_key, t_title, t_desc, _ in SUITE_THEMES:
                if t_key in self.cards:
                    self.cards[t_key].lbl_title.setText(safe_tr(t_title))
                    self.cards[t_key].lbl_desc.setText(safe_tr(t_desc))
                    self.cards[t_key]._update_style()
            return

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


SUITE_THEMES: list[tuple[str, str, str, str]] = [
    (
        "classic",
        "Classic",
        "The classic blue toolbars and menus.",
        "bars",
    ),
    (
        "paper",
        "Paper",
        "Light and calm: warm paper tones, one teal accent, rounded shapes.",
        "bars",
    ),
    (
        "paper2016",
        "Paper 2016 Ribbon",
        "Paper with tabs of commands, grouped by task, instead of toolbars.",
        "ribbon",
    ),
]


class SuiteThemePreviewCanvas(QWidget):
    """Miniature visual drawing representing Classic, Paper, or Paper 2016 Ribbon suite chrome."""

    def __init__(
        self,
        theme_key: str,
        layout_type: str = "bars",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.theme_key = theme_key
        self.layout_type = layout_type
        self.setFixedHeight(75)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w = self.width()
        h = self.height()

        if self.theme_key in ("paper", "paper2016"):
            menu_bg = QColor("#F2EFE9")
            tb_bg = QColor("#E8E4DC")
            canvas_bg = QColor("#EAE6DE")
            pane_bg = QColor("#F7F5F0")
            status_bg = QColor("#E2DDD4")
            accent = QColor("#008080")
            border_col = QColor("#CBD5E1")
        else:  # classic
            menu_bg = QColor("#E3EFFF")
            tb_bg = QColor("#CBE1FC")
            canvas_bg = QColor("#D0DCED")
            pane_bg = QColor("#FCFCF9")
            status_bg = QColor("#ECE9D8")
            accent = QColor("#3B619C")
            border_col = QColor("#7BA4E0")

        # Background canvas
        painter.fillRect(0, 0, w, h, canvas_bg)

        if self.layout_type == "ribbon":
            # Tab bar
            painter.fillRect(0, 0, w, 12, menu_bg)
            painter.fillRect(35, 1, 35, 11, QColor("#FFFFFF"))
            painter.setPen(border_col)
            painter.drawText(6, 10, "File")
            painter.drawText(40, 10, "Home")
            painter.drawText(75, 10, "Insert")

            # Ribbon panel
            painter.fillRect(0, 12, w, 22, QColor("#FFFFFF"))
            painter.setPen(border_col)
            painter.drawLine(0, 34, w, 34)

            for i in range(5):
                bx = 8 + i * 16
                painter.fillRect(bx, 15, 12, 14, tb_bg)
                if i == 0 and self.theme_key == "paper2016":
                    painter.fillRect(bx, 15, 12, 14, accent)
            painter.drawLine(96, 14, 96, 32)
            for i in range(3):
                bx = 104 + i * 16
                painter.fillRect(bx, 15, 12, 14, tb_bg)

            top_h = 35
        else:
            # Menu bar
            painter.fillRect(0, 0, w, 12, menu_bg)
            painter.setPen(border_col)
            painter.drawText(6, 10, "File")
            painter.drawText(34, 10, "Edit")
            painter.drawText(62, 10, "View")

            # Toolbar
            painter.fillRect(0, 12, w, 16, tb_bg)
            painter.drawLine(0, 28, w, 28)
            for i in range(6):
                bx = 8 + i * 14
                btn_color = accent if (i == 1 and self.theme_key == "paper") else QColor(255, 255, 255, 180)
                painter.fillRect(bx, 14, 10, 12, btn_color)

            top_h = 28

        # Status bar
        painter.fillRect(0, h - 10, w, 10, status_bg)
        painter.setPen(border_col)
        painter.drawLine(0, h - 10, w, h - 10)

        # Right-side task pane
        pane_w = 42
        painter.fillRect(w - pane_w, top_h, pane_w, h - top_h - 10, pane_bg)
        painter.drawLine(w - pane_w, top_h, w - pane_w, h - 10)

        # Document page in center
        page_x = 24
        page_y = top_h + 4
        page_w = w - pane_w - page_x - 12
        page_h = h - top_h - 18
        if page_w > 20 and page_h > 10:
            painter.fillRect(page_x, page_y, page_w, page_h, QColor("#FFFFFF"))
            painter.setPen(QColor("#E2E8F0"))
            painter.drawRect(page_x, page_y, page_w, page_h)

            painter.setPen(QColor("#CBD5E1"))
            for ly in range(page_y + 4, page_y + page_h - 3, 5):
                painter.drawLine(page_x + 4, ly, page_x + page_w - 6, ly)


class SuiteThemeCard(QFrame):
    """Clickable interactive card component showcasing a single suite appearance theme."""

    clicked = Signal(str)

    def __init__(
        self,
        theme_key: str,
        title: str,
        description: str,
        layout_type: str = "bars",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.theme_key = theme_key
        self.title_text = title
        self.desc_text = description
        self.layout_type = layout_type
        self.is_selected = False

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.preview = SuiteThemePreviewCanvas(theme_key, layout_type, self)
        layout.addWidget(self.preview)

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

        self.lbl_desc = QLabel(description, self)
        self.lbl_desc.setWordWrap(True)
        desc_font = QFont()
        desc_font.setPointSize(9)
        self.lbl_desc.setFont(desc_font)
        self.lbl_desc.setStyleSheet("color: #64748B;")
        layout.addWidget(self.lbl_desc)

        self._update_style()

    def set_selected(self, selected: bool) -> None:
        self.is_selected = selected
        self._update_style()

    def _update_style(self) -> None:
        if self.is_selected:
            self.setStyleSheet(
                "SuiteThemeCard { background: #F0F7FF; border: 2px solid #0284C7; "
                "border-radius: 6px; }"
            )
            self.lbl_badge.setText("✓ " + safe_tr("当前"))
            self.lbl_badge.setStyleSheet(
                "color: #0284C7; font-weight: bold; font-size: 10px;"
            )
        else:
            self.setStyleSheet(
                "SuiteThemeCard { background: #FFFFFF; border: 1px solid #CBD5E1; "
                "border-radius: 6px; }"
                "SuiteThemeCard:hover { border: 1px solid #38BDF8; background: #F8FAFC; }"
            )
            self.lbl_badge.setText("")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.theme_key)
        super().mousePressEvent(event)


class SuiteThemeDialog(QDialog):
    """Standalone Themes gallery dialog matching VibeOffice 3-card suite looks (Classic, Paper, Paper 2016 Ribbon)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = get_app_settings()
        self.initial_theme = str(self.settings.get_value("theme/active_theme", "classic"))
        if self.initial_theme in ("blue", "silver", "olive"):
            self.selected_theme = "classic"
        else:
            self.selected_theme = self.initial_theme

        self.cards: dict[str, SuiteThemeCard] = {}
        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        self.resize(640, 320)
        self.setMinimumSize(560, 280)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        self.lbl_header = QLabel(
            safe_tr("选择 ATBOffice 的整体外观风格。所有打开的窗口将同步即时生效。"),
            self,
        )
        self.lbl_header.setWordWrap(True)
        self.lbl_header.setStyleSheet("font-size: 13px; color: #334155;")
        root.addWidget(self.lbl_header)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        for t_key, t_title, t_desc, layout_type in SUITE_THEMES:
            card = SuiteThemeCard(
                t_key, safe_tr(t_title), safe_tr(t_desc), layout_type, self
            )
            card.clicked.connect(self._on_card_selected)
            if t_key == self.selected_theme:
                card.set_selected(True)
            self.cards[t_key] = card
            cards_layout.addWidget(card)

        root.addLayout(cards_layout)

        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        self.btn_ok = QPushButton(safe_tr("确定"), self)
        self.btn_ok.setFixedWidth(84)
        self.btn_ok.clicked.connect(self.accept)
        btn_box.addWidget(self.btn_ok)
        root.addLayout(btn_box)

    def _on_card_selected(self, theme_key: str) -> None:
        self.selected_theme = theme_key
        for k, card in self.cards.items():
            card.set_selected(k == theme_key)
        self.settings.set_value("theme/active_theme", theme_key)
        apply_theme_globally(theme_key)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("主题 — ATBOffice"))
        self.lbl_header.setText(
            safe_tr("选择 ATBOffice 的整体外观风格。所有打开的窗口将同步即时生效。")
        )
        self.btn_ok.setText(safe_tr("确定"))
        for t_key, t_title, t_desc, _ in SUITE_THEMES:
            if t_key in self.cards:
                self.cards[t_key].lbl_title.setText(safe_tr(t_title))
                self.cards[t_key].lbl_desc.setText(safe_tr(t_desc))
                self.cards[t_key]._update_style()


ThemesDialog = SuiteThemeDialog
