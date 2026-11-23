"""ATBOffice Start Center launcher window providing document hub and template gallery."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QMouseEvent,
    QPixmap,
)
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import safe_tr as core_safe_tr
from atboffice.core.recent_files import RecentItem
from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu

logger = logging.getLogger(__name__)


def safe_tr(text: str) -> str:
    """Translate UI text safely for StartCenterWindow."""
    return core_safe_tr(text)


class RecentItemWidget(QWidget):
    """Custom composite widget representing an entry in the recent documents list."""

    def __init__(
        self,
        item: RecentItem,
        on_remove: Callable[[Path], None],
        parent: QWidget | None = None,
        thumbnail: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.item = item
        self.on_remove = on_remove
        self.thumbnail = thumbnail
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # App type icon badge
        app_icons = {
            "quire": ("📘", "#2563EB"),
            "ledger": ("📗", "#16A34A"),
            "lectern": ("📙", "#EA580C"),
            "generic": ("📄", "#64748B"),
        }
        icon_symbol, _ = app_icons.get(self.item.app, app_icons["generic"])

        self.lbl_icon = QLabel(icon_symbol, self)
        font = self.lbl_icon.font()
        font.setPointSize(20)
        self.lbl_icon.setFont(font)
        self.lbl_icon.setFixedWidth(28)
        self.has_thumbnail = False
        if self.thumbnail is not None and self.thumbnail.exists():
            pix = QPixmap(str(self.thumbnail))
            if not pix.isNull():
                self.lbl_icon.setPixmap(
                    pix.scaled(64, 48, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
                )
                self.lbl_icon.setFixedSize(66, 50)
                self.lbl_icon.setStyleSheet("border: 1px solid #CBD5E1; background: #FFFFFF;")
                self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.has_thumbnail = True
        layout.addWidget(self.lbl_icon)

        # Text column (Title + path & time meta)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self.lbl_title = QLabel(self.item.title, self)
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        self.lbl_title.setFont(title_font)
        text_col.addWidget(self.lbl_title)

        meta_parts: list[str] = []
        app_names = {
            "quire": safe_tr("Quire 文本文档"),
            "ledger": safe_tr("Ledger 电子表格"),
            "lectern": safe_tr("Lectern 演示文稿"),
        }
        meta_parts.append(app_names.get(self.item.app, safe_tr("办公文档")))

        time_str = self._format_timestamp(self.item.last_opened)
        if time_str:
            meta_parts.append(time_str)

        size_str = self._format_size(self.item.size_bytes)
        if size_str:
            meta_parts.append(size_str)

        meta_parts.append(str(self.item.path.parent))

        self.lbl_meta = QLabel(" · ".join(meta_parts), self)
        meta_font = QFont()
        meta_font.setPointSize(11)
        self.lbl_meta.setFont(meta_font)
        self.lbl_meta.setStyleSheet("color: #64748B;")
        text_col.addWidget(self.lbl_meta)

        layout.addLayout(text_col, stretch=1)

        # Remove button
        self.btn_remove = QPushButton("×", self)
        self.btn_remove.setFixedSize(24, 24)
        self.btn_remove.setToolTip(safe_tr("从历史列表中移除"))
        self.btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove.setStyleSheet(
            "QPushButton { border: none; font-size: 16px; color: #94A3B8; "
            "border-radius: 12px; }"
            "QPushButton:hover { background: #F1F5F9; color: #DC2626; font-weight: bold; }"
        )
        self.btn_remove.clicked.connect(lambda: self.on_remove(self.item.path))
        layout.addWidget(self.btn_remove)

    @staticmethod
    def _format_timestamp(ts: float) -> str:
        if ts <= 0:
            return ""
        try:
            dt = datetime.fromtimestamp(ts)
            now = datetime.now()
            if dt.date() == now.date():
                return safe_tr("今天 {time}").format(time=dt.strftime("%H:%M"))
            if dt.date() == (now - timedelta(days=1)).date():
                return safe_tr("昨天 {time}").format(time=dt.strftime("%H:%M"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError):
            return ""

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes <= 0:
            return ""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.0f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"


class TemplateCard(QFrame):
    """Gallery card item representing a document template."""

    def __init__(
        self,
        title: str,
        subtitle: str,
        icon_text: str,
        on_create: Callable[[], None],
        parent: QWidget | None = None,
        template_id: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.on_create = on_create
        self.template_id = template_id
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(180, 160)
        self.setStyleSheet(
            "TemplateCard { background: #FFFFFF; border: 1px solid #E2E8F0; "
            "border-radius: 8px; }"
            "TemplateCard:hover { border: 1.5px solid #3B82F6; background: #F8FAFC; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon
        self.lbl_icon = QLabel(icon_text, self)
        font = self.lbl_icon.font()
        font.setPointSize(36)
        self.lbl_icon.setFont(font)
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_icon)

        # Title
        self.lbl_title = QLabel(title, self)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        self.lbl_title.setFont(title_font)
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_title)

        # Subtitle
        self.lbl_subtitle = QLabel(subtitle, self)
        sub_font = QFont()
        sub_font.setPointSize(10)
        self.lbl_subtitle.setFont(sub_font)
        self.lbl_subtitle.setStyleSheet("color: #64748B;")
        self.lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_subtitle)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Trigger template creation when clicked."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_create()
        super().mousePressEvent(event)


class StartCenterWindow(BaseOfficeWindow):
    """Central launcher and start hub window for the ATBOffice suite."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self.app_name = "ATBOffice"
        self.app_type = "start_center"
        super().__init__(parent)
        self.resize(1000, 680)
        self.setMinimumSize(800, 520)

        self.setAcceptDrops(True)

        # Setup macOS menu bar
        self.menu_bar: MacMenuBar = setup_mac_menu(self)

        self._build_ui()
        self._bind_start_center_actions()
        self.retranslate_ui()
        self.refresh_recent_files()

    def update_window_title(self) -> None:
        """Set window title adhering to application launcher convention."""
        self.setWindowTitle(safe_tr("启动中心 — ATBOffice"))

    def _build_ui(self) -> None:
        """Construct sidebar and stacked content layout."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Sidebar
        sidebar = self._create_sidebar()
        root_layout.addWidget(sidebar)

        # 2. Right Stacked Content
        self.stacked_widget = QStackedWidget(self)
        self.page_recent = self._create_recent_page()
        self.page_templates = self._create_templates_page()

        self.stacked_widget.addWidget(self.page_recent)     # Index 0
        self.stacked_widget.addWidget(self.page_templates)  # Index 1

        root_layout.addWidget(self.stacked_widget, stretch=1)

    def _create_sidebar(self) -> QWidget:
        """Create left navigation sidebar."""
        sidebar = QFrame(self)
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet(
            "QFrame { background-color: #F8FAFC; border-right: 1px solid #E2E8F0; }"
        )

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 20)
        layout.setSpacing(10)

        # Brand header
        self.lbl_brand_title = QLabel("ATBOffice", sidebar)
        brand_font = QFont()
        brand_font.setPointSize(20)
        brand_font.setBold(True)
        self.lbl_brand_title.setFont(brand_font)
        self.lbl_brand_title.setStyleSheet("color: #0F172A; border: none;")
        layout.addWidget(self.lbl_brand_title)

        self.lbl_brand_subtitle = QLabel(safe_tr("原生现代办公套件"), sidebar)
        sub_font = QFont()
        sub_font.setPointSize(11)
        self.lbl_brand_subtitle.setFont(sub_font)
        self.lbl_brand_subtitle.setStyleSheet(
            "color: #64748B; border: none; margin-bottom: 8px;"
        )
        layout.addWidget(self.lbl_brand_subtitle)

        # Quick Launch Section Header
        self.lbl_section_new = QLabel(safe_tr("新建"), sidebar)
        sec_font = QFont()
        sec_font.setPointSize(11)
        sec_font.setBold(True)
        self.lbl_section_new.setFont(sec_font)
        self.lbl_section_new.setStyleSheet(
            "color: #94A3B8; border: none; margin-top: 8px;"
        )
        layout.addWidget(self.lbl_section_new)

        # Quick Launch Buttons
        btn_style = (
            "QPushButton { text-align: left; padding: 8px 12px; font-size: 13px; "
            "border: 1px solid transparent; border-radius: 6px; "
            "background: transparent; color: #1E293B; }"
            "QPushButton:hover { background: #EDF2F7; border-color: #CBD5E1; }"
            "QPushButton:pressed { background: #E2E8F0; }"
        )

        self.btn_new_quire = QPushButton("📘  " + safe_tr("Quire 文本文档"), sidebar)
        self.btn_new_quire.setStyleSheet(btn_style)
        self.btn_new_quire.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_quire.clicked.connect(self._on_new_quire_clicked)
        layout.addWidget(self.btn_new_quire)

        self.btn_new_ledger = QPushButton("📗  " + safe_tr("Ledger 电子表格"), sidebar)
        self.btn_new_ledger.setStyleSheet(btn_style)
        self.btn_new_ledger.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_ledger.clicked.connect(self._on_new_ledger_clicked)
        layout.addWidget(self.btn_new_ledger)

        self.btn_new_lectern = QPushButton("📙  " + safe_tr("Lectern 演示文稿"), sidebar)
        self.btn_new_lectern.setStyleSheet(btn_style)
        self.btn_new_lectern.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_lectern.clicked.connect(self._on_new_lectern_clicked)
        layout.addWidget(self.btn_new_lectern)

        # Action: Open Local File
        layout.addSpacing(6)
        self.btn_open_file = QPushButton("📂  " + safe_tr("打开本地文件..."), sidebar)
        open_style = (
            "QPushButton { text-align: left; padding: 8px 12px; font-size: 13px; "
            "font-weight: bold; border: 1px solid #CBD5E1; border-radius: 6px; "
            "background: #FFFFFF; color: #1E293B; }"
            "QPushButton:hover { background: #F1F5F9; border-color: #94A3B8; }"
            "QPushButton:pressed { background: #E2E8F0; }"
        )
        self.btn_open_file.setStyleSheet(open_style)
        self.btn_open_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_file.clicked.connect(self._on_open_file_clicked)
        layout.addWidget(self.btn_open_file)

        # Navigation Toggles Section Header
        layout.addSpacing(12)
        self.lbl_section_nav = QLabel(safe_tr("视图"), sidebar)
        self.lbl_section_nav.setFont(sec_font)
        self.lbl_section_nav.setStyleSheet("color: #94A3B8; border: none;")
        layout.addWidget(self.lbl_section_nav)

        nav_style = (
            "QPushButton { text-align: left; padding: 8px 12px; font-size: 13px; "
            "border: 1px solid transparent; border-radius: 6px; "
            "background: transparent; color: #334155; }"
            "QPushButton:hover { background: #EDF2F7; }"
            "QPushButton:checked { background: #E0E7FF; color: #1D4ED8; "
            "font-weight: bold; border-color: #BFDBFE; }"
        )

        self.btn_nav_recent = QPushButton("🕒  " + safe_tr("最近文档"), sidebar)
        self.btn_nav_recent.setCheckable(True)
        self.btn_nav_recent.setChecked(True)
        self.btn_nav_recent.setStyleSheet(nav_style)
        self.btn_nav_recent.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_recent.clicked.connect(self._on_nav_recent_clicked)
        layout.addWidget(self.btn_nav_recent)

        self.btn_nav_templates = QPushButton("🗂️  " + safe_tr("模板库"), sidebar)
        self.btn_nav_templates.setCheckable(True)
        self.btn_nav_templates.setChecked(False)
        self.btn_nav_templates.setStyleSheet(nav_style)
        self.btn_nav_templates.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_templates.clicked.connect(self._on_nav_templates_clicked)
        layout.addWidget(self.btn_nav_templates)

        layout.addStretch(1)

        # Bottom Utilities (Themes, Settings, About, Update)
        bottom_box = QVBoxLayout()
        bottom_box.setSpacing(6)

        row_top = QHBoxLayout()
        row_top.setSpacing(6)
        row_bot = QHBoxLayout()
        row_bot.setSpacing(6)

        util_style = (
            "QPushButton { padding: 6px 8px; font-size: 12px; border: 1px solid #E2E8F0; "
            "border-radius: 6px; background: #FFFFFF; color: #475569; }"
            "QPushButton:hover { background: #F1F5F9; color: #0F172A; border-color: #CBD5E1; }"
        )

        self.btn_themes = QPushButton(safe_tr("主题"), sidebar)
        self.btn_themes.setStyleSheet(util_style)
        self.btn_themes.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_themes.clicked.connect(self.show_theme_dialog)
        row_top.addWidget(self.btn_themes)

        self.btn_settings = QPushButton(safe_tr("设置"), sidebar)
        self.btn_settings.setStyleSheet(util_style)
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.clicked.connect(self._on_settings_clicked)
        row_top.addWidget(self.btn_settings)

        self.btn_about = QPushButton(safe_tr("关于"), sidebar)
        self.btn_about.setStyleSheet(util_style)
        self.btn_about.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_about.clicked.connect(self.show_about)
        row_bot.addWidget(self.btn_about)

        self.btn_update = QPushButton(safe_tr("检查更新"), sidebar)
        self.btn_update.setStyleSheet(util_style)
        self.btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_update.clicked.connect(self.check_for_updates)
        row_bot.addWidget(self.btn_update)

        bottom_box.addLayout(row_top)
        bottom_box.addLayout(row_bot)
        layout.addLayout(bottom_box)
        return sidebar

    def _create_recent_page(self) -> QWidget:
        """Create right-side Recent Files list view page."""
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(16)

        # Top Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        self.lbl_recent_title = QLabel(safe_tr("最近打开的文档"), page)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        self.lbl_recent_title.setFont(title_font)
        self.lbl_recent_title.setStyleSheet("color: #0F172A;")
        top_bar.addWidget(self.lbl_recent_title)

        top_bar.addStretch(1)

        self.btn_clear_recent = QPushButton(safe_tr("清空历史"), page)
        self.btn_clear_recent.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_recent.setStyleSheet(
            "QPushButton { padding: 5px 12px; font-size: 12px; border: 1px solid #CBD5E1; "
            "border-radius: 6px; background: #FFFFFF; color: #475569; }"
            "QPushButton:hover { background: #FEE2E2; border-color: #F87171; color: #B91C1C; }"
            "QPushButton:disabled { color: #CBD5E1; border-color: #E2E8F0; "
            "background: transparent; }"
        )
        self.btn_clear_recent.clicked.connect(self._on_clear_recent_clicked)
        top_bar.addWidget(self.btn_clear_recent)

        layout.addLayout(top_bar)

        # Empty State Banner
        self.empty_state_widget = QWidget(page)
        empty_layout = QVBoxLayout(self.empty_state_widget)
        empty_layout.setContentsMargins(20, 60, 20, 60)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(12)

        lbl_empty_icon = QLabel("📁", self.empty_state_widget)
        empty_icon_font = lbl_empty_icon.font()
        empty_icon_font.setPointSize(48)
        lbl_empty_icon.setFont(empty_icon_font)
        lbl_empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(lbl_empty_icon)

        self.lbl_empty_main = QLabel(safe_tr("暂无最近打开的文档"), self.empty_state_widget)
        empty_main_font = QFont()
        empty_main_font.setPointSize(15)
        empty_main_font.setBold(True)
        self.lbl_empty_main.setFont(empty_main_font)
        self.lbl_empty_main.setStyleSheet("color: #334155;")
        self.lbl_empty_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.lbl_empty_main)

        self.lbl_empty_desc = QLabel(
            safe_tr("拖拽文件到此处，或点击左侧“打开本地文件”开始工作。"),
            self.empty_state_widget,
        )
        self.lbl_empty_desc.setStyleSheet("color: #64748B; font-size: 13px;")
        self.lbl_empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.lbl_empty_desc)

        layout.addWidget(self.empty_state_widget)

        # Recent Items List
        self.recent_list_widget = QListWidget(page)
        self.recent_list_widget.setStyleSheet(
            "QListWidget { border: 1px solid #E2E8F0; border-radius: 8px; "
            "background: #FFFFFF; outline: none; }"
            "QListWidget::item { border-bottom: 1px solid #F1F5F9; padding: 2px 0px; }"
            "QListWidget::item:hover { background: #F8FAFC; }"
            "QListWidget::item:selected { background: #EFF6FF; }"
        )
        self.recent_list_widget.itemActivated.connect(self._on_recent_item_activated)
        layout.addWidget(self.recent_list_widget, stretch=1)

        # Document Recovery: drafts left by a session that did not close cleanly
        self.recovery_box = QFrame(page)
        self.recovery_box.setObjectName("recoveryBox")
        self.recovery_box.setStyleSheet(
            "#recoveryBox { background: #FFFBEB; border: 1px solid #FCD34D; border-radius: 8px; }"
        )
        rec_layout = QVBoxLayout(self.recovery_box)
        rec_layout.setContentsMargins(12, 8, 12, 8)
        self.lbl_recovery_title = QLabel(self.recovery_box)
        rec_font = QFont()
        rec_font.setBold(True)
        self.lbl_recovery_title.setFont(rec_font)
        rec_layout.addWidget(self.lbl_recovery_title)
        self.recovery_rows = QVBoxLayout()
        rec_layout.addLayout(self.recovery_rows)
        self.recovery_box.setVisible(False)
        layout.insertWidget(1, self.recovery_box)

        return page

    def _create_templates_page(self) -> QWidget:
        """Create right-side Templates gallery view page."""
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(16)

        self.lbl_templates_title = QLabel(safe_tr("模板库与新建"), page)
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        self.lbl_templates_title.setFont(title_font)
        self.lbl_templates_title.setStyleSheet("color: #0F172A;")
        layout.addWidget(self.lbl_templates_title)

        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget(scroll)
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 12, 12)
        scroll_layout.setSpacing(20)

        from atboffice.core.templates import TemplateRegistry
        from atboffice.core.window_manager import WindowManager

        registry = TemplateRegistry.get_instance()
        self.template_cards: list[TemplateCard] = []
        sections = (
            ("quire", "Quire " + safe_tr("文本文档"), safe_tr("空白文档"),
             safe_tr("标准空白页面"), "📄"),
            ("ledger", "Ledger " + safe_tr("电子表格"), safe_tr("空白工作簿"),
             safe_tr("标准多标签表格"), "📗"),
            ("lectern", "Lectern " + safe_tr("演示文稿"), safe_tr("空白幻灯片"),
             safe_tr("16:9 宽屏演示"), "📙"),
        )
        for app, title, blank_title, blank_sub, blank_icon in sections:
            opener = getattr(WindowManager.get_instance(), f"open_{app}")
            items: list[tuple[Any, ...]] = [
                (blank_title, blank_sub, blank_icon, lambda o=opener: o(), None)
            ]
            for info in registry.list_templates(app):
                items.append((
                    safe_tr(info.name),
                    safe_tr(info.description or info.category or ""),
                    info.icon or "📄",
                    lambda o=opener, tid=info.id: o(template_id=tid),
                    info.id,
                ))
            self._add_template_section(scroll_layout, title=title, items=items)

        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        return page

    def _add_template_section(
        self,
        container_layout: QVBoxLayout,
        title: str,
        items: list[tuple[Any, ...]],
    ) -> None:
        """Add a category row of template cards."""
        sec_title = QLabel(title)
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        sec_title.setFont(font)
        sec_title.setStyleSheet("color: #334155; margin-top: 8px;")
        container_layout.addWidget(sec_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        per_row = 5
        for idx, item in enumerate(items):
            card_title, subtitle, icon, callback = item[0], item[1], item[2], item[3]
            tid = item[4] if len(item) > 4 else None
            card = TemplateCard(card_title, subtitle, icon, callback, template_id=tid)
            if hasattr(self, "template_cards"):
                self.template_cards.append(card)
            grid.addWidget(card, idx // per_row, idx % per_row)
        grid.setColumnStretch(per_row, 1)
        container_layout.addLayout(grid)

    # Menu commands the launcher can execute; every other editor command is disabled.
    _SUPPORTED_MENU_ACTIONS: frozenset[str] = frozenset(
        {
            "new",
            "open",
            "close",
            "tools_options",
            "theme_luna_blue",
            "theme_luna_silver",
            "theme_luna_olive",
            "theme_classic",
            "theme_selector",
            "window_minimize",
            "window_zoom",
            "window_bring_all",
            "help",
            "help_assistant",
            "check_updates",
            "about",
        }
    )

    def _bind_start_center_actions(self) -> None:
        """Bind launcher handlers and cleanly disable editor-only menu commands."""
        registry = self.menu_bar.action_registry
        registry.set_handler("new", self._on_nav_templates_clicked)
        registry.set_handler("open", self.open_file_dialog)
        registry.set_handler("close", self.close)
        registry.set_handler("tools_options", self._on_settings_clicked)
        registry.set_handler("about", self.show_about)
        registry.set_handler("help", self.show_help)

        reason = safe_tr("启动中心不支持此命令，请先新建或打开一份文档")
        canonical_ids = {registry.resolve_id(key) for key in self.menu_bar.action_map}
        for action_id in canonical_ids - self._SUPPORTED_MENU_ACTIONS:
            spec = registry.get_spec(action_id)
            if spec is not None:
                spec.disabled_reason = reason
            registry.set_enabled(action_id, False)

    # -------------------------------------------------------------------------
    # Navigation and Action Slots
    # -------------------------------------------------------------------------
    def _on_nav_recent_clicked(self) -> None:
        self.stacked_widget.setCurrentIndex(0)
        self.btn_nav_recent.setChecked(True)
        self.btn_nav_templates.setChecked(False)

    def _on_nav_templates_clicked(self) -> None:
        self.stacked_widget.setCurrentIndex(1)
        self.btn_nav_templates.setChecked(True)
        self.btn_nav_recent.setChecked(False)

    def _on_new_quire_clicked(self) -> None:
        from atboffice.core.window_manager import WindowManager

        WindowManager.get_instance().open_quire()

    def _on_new_ledger_clicked(self) -> None:
        from atboffice.core.window_manager import WindowManager

        WindowManager.get_instance().open_ledger()

    def _on_new_lectern_clicked(self) -> None:
        from atboffice.core.window_manager import WindowManager

        WindowManager.get_instance().open_lectern()

    def _on_open_file_clicked(self) -> None:
        """Prompt user to choose an office file and open via WindowManager."""
        file_filters = safe_tr(
            "所有支持的格式 (*.docx *.doc *.odt *.rtf *.txt *.html *.htm *.xlsx *.xls *.csv *.tsv "
            "*.ods *.pptx *.ppt *.odp);;"
            "文本文档 (*.docx *.doc *.odt *.rtf *.txt *.html *.htm);;"
            "电子表格 (*.xlsx *.xls *.csv *.tsv *.ods);;"
            "演示文稿 (*.pptx *.ppt *.odp);;"
            "所有文件 (*.*)"
        )
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            safe_tr("打开文档"),
            "",
            file_filters,
        )
        if file_path:
            from atboffice.core.window_manager import WindowManager

            WindowManager.get_instance().open_file_auto(Path(file_path).resolve())

    def open_file_dialog(self) -> bool:
        """Override BaseOfficeWindow hook for native menu Open action."""
        self._on_open_file_clicked()
        return True

    def open_file(self, file_path: str | Path) -> bool:
        """Override BaseOfficeWindow hook to route through WindowManager."""
        from atboffice.core.window_manager import WindowManager

        WindowManager.get_instance().open_file_auto(Path(file_path).resolve())
        return True

    def _on_clear_recent_clicked(self) -> None:
        """Prompt confirmation and clear all recent document history."""
        reply = QMessageBox.question(
            self,
            safe_tr("清空历史记录"),
            safe_tr("确定要从最近文档列表中移除所有记录吗？\n（计算机上的本地文件不会被删除）"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from atboffice.core.window_manager import WindowManager

            WindowManager.get_instance().recent_files.clear_all()
            self.refresh_recent_files()

    def _remove_recent_item(self, path: Path) -> None:
        """Remove a single file entry from recent history."""
        from atboffice.core.window_manager import WindowManager

        WindowManager.get_instance().recent_files.remove_file(path)
        self.refresh_recent_files()

    def _on_recent_item_activated(self, item: QListWidgetItem) -> None:
        """Handle activating a recent file entry; prompts removal if missing."""
        if item is None:
            return

        path_str = item.data(Qt.ItemDataRole.UserRole)
        if not path_str:
            return

        path = Path(path_str).resolve()
        from atboffice.core.window_manager import WindowManager

        wm = WindowManager.get_instance()

        if not path.exists():
            reply = QMessageBox.question(
                self,
                safe_tr("文件不存在"),
                safe_tr("找不到指定的文件：\n{path}\n\n是否将其从最近历史记录中移除？").format(
                    path=path
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                wm.recent_files.remove_file(path)
                self.refresh_recent_files()
            return

        wm.open_file_auto(path)

    def _on_settings_clicked(self) -> None:
        """Open the multi-tab Options preference dialog."""
        if self.show_options_dialog() == QDialog.DialogCode.Accepted:
            self.refresh_recent_files()

    def show_theme_dialog(self) -> int:
        """Open the standalone SuiteThemeDialog gallery."""
        from atboffice.ui.dialogs.theme_dialog import SuiteThemeDialog

        dlg = SuiteThemeDialog(self)
        return dlg.exec()

    def show_license_dialog(self) -> int:
        """Open the Open Source Licenses dialog."""
        from atboffice.ui.dialogs.license_dialog import LicenseDialog

        dlg = LicenseDialog(self)
        return dlg.exec()

    def show_update_dialog(self) -> int:
        """Open the software update dialog."""
        from atboffice.ui.dialogs.update_dialog import UpdateDialog

        dlg = UpdateDialog(parent=self)
        return dlg.exec()

    def check_for_updates(self) -> None:
        """Check for application updates."""
        from atboffice.core.updater import check_for_updates

        check_for_updates(parent=self, manual=True)

    def show_about(self) -> None:
        """Display application about dialog with license and update links."""
        from atboffice.ui.dialogs.about_dialog import AboutDialog

        dlg = AboutDialog(self)
        dlg.exec()

    # -------------------------------------------------------------------------
    # Drag and Drop Implementation
    # -------------------------------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drag events carrying file URLs."""
        mime_data = event.mimeData()
        if mime_data is not None and mime_data.hasUrls():
            try:
                event.acceptProposedAction()
            except Exception:
                pass
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """Accept move events during URL drag-over."""
        mime_data = event.mimeData()
        if mime_data is not None and mime_data.hasUrls():
            try:
                event.acceptProposedAction()
            except Exception:
                pass
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        """Extract dropped local file paths and route via WindowManager."""
        mime_data = event.mimeData()
        if mime_data is None or not mime_data.hasUrls():
            event.ignore()
            return

        from atboffice.core.window_manager import WindowManager

        wm = WindowManager.get_instance()
        opened_any = False

        for url in mime_data.urls():
            local_path = url.toLocalFile()
            if local_path:
                p = Path(local_path).resolve()
                wm.open_file_auto(p)
                opened_any = True

        if opened_any:
            try:
                event.acceptProposedAction()
            except Exception:
                pass
            event.accept()
        else:
            event.ignore()

    # -------------------------------------------------------------------------
    # Public Refresh and i18n
    # -------------------------------------------------------------------------
    def refresh_recovery_drafts(self, recovery_dir: Path | None = None) -> int:
        """List recoverable drafts (badge rows with Open / Discard); returns the count."""
        from atboffice.core.recovery_service import list_orphan_drafts

        if not hasattr(self, "recovery_rows"):
            return 0
        while self.recovery_rows.count():
            child = self.recovery_rows.takeAt(0)
            if child.widget() is not None:
                child.widget().deleteLater()
        drafts = list_orphan_drafts(recovery_dir)
        self._recovery_dir_override = recovery_dir
        self.lbl_recovery_title.setText(
            safe_tr("文档恢复：发现 {0} 个未保存的恢复版本").format(len(drafts))
        )
        for draft in drafts[:8]:
            row = QWidget(self.recovery_box)
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            when = datetime.fromtimestamp(draft.modified).strftime("%Y-%m-%d %H:%M")
            lbl = QLabel(f"🛟 {draft.name}{draft.ext}  ·  {when}", row)
            btn_open = QPushButton(safe_tr("打开"), row)
            btn_open.setObjectName("recoveryOpen")
            btn_discard = QPushButton(safe_tr("放弃"), row)
            btn_discard.setObjectName("recoveryDiscard")
            btn_open.clicked.connect(lambda _c=False, d=draft: self._open_recovery_draft(d))
            btn_discard.clicked.connect(lambda _c=False, d=draft: self._discard_recovery_draft(d))
            h.addWidget(lbl, 1)
            h.addWidget(btn_open)
            h.addWidget(btn_discard)
            self.recovery_rows.addWidget(row)
        self.recovery_box.setVisible(bool(drafts))
        return len(drafts)

    def _open_recovery_draft(self, draft: Any) -> None:
        from atboffice.core.window_manager import WindowManager

        try:
            WindowManager.get_instance().open_file_auto(draft.path)
        except Exception as exc:
            QMessageBox.warning(
                self, safe_tr("文档恢复"), safe_tr("无法打开恢复版本：{0}").format(exc)
            )

    def _discard_recovery_draft(self, draft: Any) -> None:
        res = QMessageBox.question(
            self,
            safe_tr("文档恢复"),
            safe_tr("永久删除恢复版本“{0}”？此操作无法撤销。").format(draft.name + draft.ext),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res != QMessageBox.StandardButton.Yes:
            return
        try:
            draft.path.unlink(missing_ok=True)
        except OSError:
            pass
        self.refresh_recovery_drafts(getattr(self, "_recovery_dir_override", None))

    def refresh_recent_files(self) -> None:
        """Synchronize the recent documents list with RecentFilesManager."""
        from atboffice.core.window_manager import WindowManager

        self.refresh_recovery_drafts(getattr(self, "_recovery_dir_override", None))

        wm = WindowManager.get_instance()
        entries = wm.recent_files.get_entries()

        self.recent_list_widget.clear()

        if not entries:
            self.empty_state_widget.setVisible(True)
            self.recent_list_widget.setVisible(False)
            self.btn_clear_recent.setEnabled(False)
            return

        self.empty_state_widget.setVisible(False)
        self.recent_list_widget.setVisible(True)
        self.btn_clear_recent.setEnabled(True)

        for entry in entries:
            list_item = QListWidgetItem(self.recent_list_widget)
            list_item.setData(Qt.ItemDataRole.UserRole, str(entry.path))
            thumb = wm.recent_files.thumbnail_for(entry.path)
            item_widget = RecentItemWidget(
                item=entry,
                on_remove=self._remove_recent_item,
                parent=self.recent_list_widget,
                thumbnail=thumb,
            )
            list_item.setSizeHint(QSize(0, 66 if item_widget.has_thumbnail else 56))
            self.recent_list_widget.setItemWidget(list_item, item_widget)

    def retranslate_ui(self) -> None:
        """Update localized UI text across all widgets."""
        self.update_window_title()

        if hasattr(self, "lbl_brand_subtitle"):
            self.lbl_brand_subtitle.setText(safe_tr("原生现代办公套件"))
        if hasattr(self, "lbl_section_new"):
            self.lbl_section_new.setText(safe_tr("新建"))
        if hasattr(self, "btn_new_quire"):
            self.btn_new_quire.setText("📘  " + safe_tr("Quire 文本文档"))
        if hasattr(self, "btn_new_ledger"):
            self.btn_new_ledger.setText("📗  " + safe_tr("Ledger 电子表格"))
        if hasattr(self, "btn_new_lectern"):
            self.btn_new_lectern.setText("📙  " + safe_tr("Lectern 演示文稿"))
        if hasattr(self, "btn_open_file"):
            self.btn_open_file.setText("📂  " + safe_tr("打开本地文件..."))
        if hasattr(self, "lbl_section_nav"):
            self.lbl_section_nav.setText(safe_tr("视图"))
        if hasattr(self, "btn_nav_recent"):
            self.btn_nav_recent.setText("🕒  " + safe_tr("最近文档"))
        if hasattr(self, "btn_nav_templates"):
            self.btn_nav_templates.setText("🗂️  " + safe_tr("模板库"))
        if hasattr(self, "btn_themes"):
            self.btn_themes.setText(safe_tr("主题"))
        if hasattr(self, "btn_settings"):
            self.btn_settings.setText(safe_tr("设置"))
        if hasattr(self, "btn_about"):
            self.btn_about.setText(safe_tr("关于"))
        if hasattr(self, "btn_update"):
            self.btn_update.setText(safe_tr("检查更新"))
        if hasattr(self, "lbl_recent_title"):
            self.lbl_recent_title.setText(safe_tr("最近打开的文档"))
        if hasattr(self, "btn_clear_recent"):
            self.btn_clear_recent.setText(safe_tr("清空历史"))
        if hasattr(self, "lbl_empty_main"):
            self.lbl_empty_main.setText(safe_tr("暂无最近打开的文档"))
        if hasattr(self, "lbl_empty_desc"):
            self.lbl_empty_desc.setText(
                safe_tr("拖拽文件到此处，或点击左侧“打开本地文件”开始工作。")
            )
        if hasattr(self, "lbl_templates_title"):
            self.lbl_templates_title.setText(safe_tr("模板库与新建"))

        self.refresh_recent_files()
