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

from atboffice.core.i18n import safe_tr
from atboffice.core.recent_files import RecentItem
from atboffice.ui.icons import get_office_icon, get_office_pixmap
from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu
from atboffice.ui.styles.luna_2003 import theme_tokens, ui_font

logger = logging.getLogger(__name__)


#: Icon of each editor, in the recent list, the template cards and the sidebar.
APP_ICONS: dict[str, str] = {
    "quire": "app_quire",
    "ledger": "app_ledger",
    "lectern": "app_lectern",
    "generic": "app_suite",
}


def start_center_stylesheet(theme: str | None = "blue") -> str:
    """Office 2003 task-pane look for the Start Center, in the colors of ``theme``."""
    t = theme_tokens(theme)
    return f"""
    #scSidebar {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t.tb_a}, stop:1 {t.tb_b});
        border-right: 1px solid {t.tb_border};
    }}
    #scBrand {{ color: {t.grip}; }}
    #scSubtitle {{ color: #4D4D4D; }}
    QLabel[scSection="true"] {{
        color: {t.grip};
        font-weight: bold;
        border-bottom: 1px solid {t.tb_c};
        padding: 6px 0 2px 0;
    }}
    QPushButton[scLink="true"] {{
        text-align: left;
        padding: 4px 6px;
        border: 1px solid transparent;
        border-radius: 2px;
        background: transparent;
        color: #0033CC;
    }}
    QPushButton[scLink="true"]:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t.hot_a}, stop:1 {t.hot_b});
        border-color: {t.hot_border};
        color: #000000;
    }}
    QPushButton[scLink="true"]:checked {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t.chk_a}, stop:1 {t.chk_b});
        border-color: {t.hot_border};
        color: #000000;
        font-weight: bold;
    }}
    QLabel[scTitle="true"] {{ color: {t.grip}; }}
    QLabel[scMuted="true"] {{ color: #555555; }}
    #scRecentList {{
        background: #FFFFFF;
        border: 1px solid {t.tb_border};
        outline: none;
    }}
    #scRecentList::item {{ border-bottom: 1px solid #E4E8F0; }}
    #scRecentList::item:hover {{ background: {t.hot_a}; }}
    #scRecentList::item:selected {{ background: {t.menu_hot}; color: #000000; }}
    #scThumb {{ border: 1px solid #A0A0A0; background: #FFFFFF; }}
    QPushButton#scRemove {{
        border: 1px solid transparent;
        border-radius: 2px;
        background: transparent;
        color: #707070;
        font-size: 14px;
    }}
    QPushButton#scRemove:hover {{
        border-color: {t.hot_border};
        background: {t.hot_a};
        color: #C00000;
    }}
    TemplateCard {{
        background: #FFFFFF;
        border: 1px solid {t.tb_edge};
        border-radius: 2px;
    }}
    TemplateCard:hover {{
        background: {t.hot_a};
        border: 1px solid {t.hot_border};
    }}
    #recoveryBox {{
        background: #FFFFE1;
        border: 1px solid #ACA899;
    }}
    """


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

        # Editor icon, replaced by the document's thumbnail when there is one
        icon_name = APP_ICONS.get(self.item.app, APP_ICONS["generic"])
        self.lbl_icon = QLabel(self)
        self.lbl_icon.setPixmap(get_office_pixmap(icon_name, 32))
        self.lbl_icon.setFixedWidth(34)
        self.has_thumbnail = False
        if self.thumbnail is not None and self.thumbnail.exists():
            pix = QPixmap(str(self.thumbnail))
            if not pix.isNull():
                self.lbl_icon.setPixmap(
                    pix.scaled(
                        64,
                        48,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self.lbl_icon.setFixedSize(66, 50)
                self.lbl_icon.setObjectName("scThumb")
                self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.has_thumbnail = True
        layout.addWidget(self.lbl_icon)

        # Text column (Title + path & time meta)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self.lbl_title = QLabel(self.item.title, self)
        title_font = ui_font(10, bold=True)
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
        self.lbl_meta.setFont(ui_font(8.5))
        self.lbl_meta.setProperty("scMuted", True)
        text_col.addWidget(self.lbl_meta)

        layout.addLayout(text_col, stretch=1)

        # Remove button
        self.btn_remove = QPushButton("×", self)
        self.btn_remove.setObjectName("scRemove")
        self.btn_remove.setFixedSize(22, 22)
        self.btn_remove.setToolTip(safe_tr("从历史列表中移除"))
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
        self.setFixedSize(168, 132)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon: ``icon_text`` names a vector icon (an editor's, by default)
        self.lbl_icon = QLabel(self)
        self.lbl_icon.setPixmap(get_office_pixmap(icon_text, 32))
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_icon)

        # Title
        self.lbl_title = QLabel(title, self)
        self.lbl_title.setFont(ui_font(9, bold=True))
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setWordWrap(True)
        layout.addWidget(self.lbl_title)

        # Subtitle
        self.lbl_subtitle = QLabel(subtitle, self)
        self.lbl_subtitle.setFont(ui_font(8))
        self.lbl_subtitle.setProperty("scMuted", True)
        self.lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_subtitle.setWordWrap(True)
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
        self.apply_theme(self.current_theme)
        self._bind_start_center_actions()
        self.retranslate_ui()
        self.refresh_recent_files()

    def apply_theme(self, theme_name: str) -> None:
        super().apply_theme(theme_name)
        central = self.centralWidget()
        if central is not None:
            central.setStyleSheet(start_center_stylesheet(theme_name))

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

        self.stacked_widget.addWidget(self.page_recent)  # Index 0
        self.stacked_widget.addWidget(self.page_templates)  # Index 1

        root_layout.addWidget(self.stacked_widget, stretch=1)

    def _create_sidebar(self) -> QWidget:
        """Create the left task pane: new documents, open, views and utilities."""
        sidebar = QFrame(self)
        sidebar.setObjectName("scSidebar")
        sidebar.setFixedWidth(232)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(4)

        # Brand header
        self.lbl_brand_title = QLabel("ATBOffice", sidebar)
        self.lbl_brand_title.setObjectName("scBrand")
        self.lbl_brand_title.setFont(ui_font(16, bold=True))
        layout.addWidget(self.lbl_brand_title)

        self.lbl_brand_subtitle = QLabel(sidebar)
        self.lbl_brand_subtitle.setObjectName("scSubtitle")
        layout.addWidget(self.lbl_brand_subtitle)
        layout.addSpacing(8)

        def section() -> QLabel:
            label = QLabel(sidebar)
            label.setProperty("scSection", True)
            layout.addWidget(label)
            return label

        def link(icon: str, slot: Callable[[], Any], *, checkable: bool = False) -> QPushButton:
            btn = QPushButton(sidebar)
            btn.setProperty("scLink", True)
            btn.setIcon(get_office_icon(icon))
            btn.setIconSize(QSize(16, 16))
            btn.setCheckable(checkable)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            layout.addWidget(btn)
            return btn

        self.lbl_section_new = section()
        self.btn_new_quire = link(APP_ICONS["quire"], self._on_new_quire_clicked)
        self.btn_new_ledger = link(APP_ICONS["ledger"], self._on_new_ledger_clicked)
        self.btn_new_lectern = link(APP_ICONS["lectern"], self._on_new_lectern_clicked)
        self.btn_open_file = link("open", self._on_open_file_clicked)

        layout.addSpacing(8)
        self.lbl_section_nav = section()
        self.btn_nav_recent = link("open", self._on_nav_recent_clicked, checkable=True)
        self.btn_nav_recent.setChecked(True)
        self.btn_nav_templates = link("templates", self._on_nav_templates_clicked, checkable=True)

        layout.addStretch(1)

        # Utilities: plain Office buttons
        grid = QGridLayout()
        grid.setSpacing(6)
        self.btn_themes = QPushButton(sidebar)
        self.btn_themes.clicked.connect(self.show_theme_dialog)
        self.btn_settings = QPushButton(sidebar)
        self.btn_settings.clicked.connect(self._on_settings_clicked)
        self.btn_about = QPushButton(sidebar)
        self.btn_about.clicked.connect(self.show_about)
        self.btn_update = QPushButton(sidebar)
        self.btn_update.clicked.connect(self.check_for_updates)
        grid.addWidget(self.btn_themes, 0, 0)
        grid.addWidget(self.btn_settings, 0, 1)
        grid.addWidget(self.btn_about, 1, 0)
        grid.addWidget(self.btn_update, 1, 1)
        layout.addLayout(grid)
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
        self.lbl_recent_title.setFont(ui_font(14, bold=True))
        self.lbl_recent_title.setProperty("scTitle", True)
        top_bar.addWidget(self.lbl_recent_title)

        top_bar.addStretch(1)

        self.btn_clear_recent = QPushButton(safe_tr("清空历史"), page)
        self.btn_clear_recent.clicked.connect(self._on_clear_recent_clicked)
        top_bar.addWidget(self.btn_clear_recent)

        layout.addLayout(top_bar)

        # Empty State Banner
        self.empty_state_widget = QWidget(page)
        empty_layout = QVBoxLayout(self.empty_state_widget)
        empty_layout.setContentsMargins(20, 60, 20, 60)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(12)

        lbl_empty_icon = QLabel(self.empty_state_widget)
        lbl_empty_icon.setPixmap(get_office_pixmap("open", 48))
        lbl_empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(lbl_empty_icon)

        self.lbl_empty_main = QLabel(safe_tr("暂无最近打开的文档"), self.empty_state_widget)
        self.lbl_empty_main.setFont(ui_font(12, bold=True))
        self.lbl_empty_main.setProperty("scTitle", True)
        self.lbl_empty_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.lbl_empty_main)

        self.lbl_empty_desc = QLabel(
            safe_tr("拖拽文件到此处，或点击左侧“打开本地文件”开始工作。"),
            self.empty_state_widget,
        )
        self.lbl_empty_desc.setProperty("scMuted", True)
        self.lbl_empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.lbl_empty_desc)

        layout.addWidget(self.empty_state_widget)

        # Recent Items List
        self.recent_list_widget = QListWidget(page)
        self.recent_list_widget.setObjectName("scRecentList")
        self.recent_list_widget.itemActivated.connect(self._on_recent_item_activated)
        layout.addWidget(self.recent_list_widget, stretch=1)

        # Document Recovery: drafts left by a session that did not close cleanly
        self.recovery_box = QFrame(page)
        self.recovery_box.setObjectName("recoveryBox")
        rec_layout = QVBoxLayout(self.recovery_box)
        rec_layout.setContentsMargins(12, 8, 12, 8)
        self.lbl_recovery_title = QLabel(self.recovery_box)
        self.lbl_recovery_title.setFont(ui_font(9, bold=True))
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
        self.lbl_templates_title.setFont(ui_font(14, bold=True))
        self.lbl_templates_title.setProperty("scTitle", True)
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
            (
                "quire",
                "Quire " + safe_tr("文本文档"),
                safe_tr("空白文档"),
                safe_tr("标准空白页面"),
                APP_ICONS["quire"],
            ),
            (
                "ledger",
                "Ledger " + safe_tr("电子表格"),
                safe_tr("空白工作簿"),
                safe_tr("标准多标签表格"),
                APP_ICONS["ledger"],
            ),
            (
                "lectern",
                "Lectern " + safe_tr("演示文稿"),
                safe_tr("空白幻灯片"),
                safe_tr("16:9 宽屏演示"),
                APP_ICONS["lectern"],
            ),
        )

        def opener(app: str, template_id: str | None = None) -> Callable[[], Any]:
            # Resolve the WindowManager method at click time, not when the page is built
            def open_it() -> Any:
                open_fn = getattr(WindowManager.get_instance(), f"open_{app}")
                return open_fn(template_id=template_id) if template_id else open_fn()

            return open_it

        for app, title, blank_title, blank_sub, blank_icon in sections:
            items: list[tuple[Any, ...]] = [(blank_title, blank_sub, blank_icon, opener(app), None)]
            for info in registry.list_templates(app):
                items.append(
                    (
                        safe_tr(info.name),
                        safe_tr(info.description or info.category or ""),
                        blank_icon,
                        opener(app, info.id),
                        info.id,
                    )
                )
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
        sec_title.setProperty("scSection", True)
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
            self.btn_new_quire.setText(safe_tr("Quire 文本文档"))
        if hasattr(self, "btn_new_ledger"):
            self.btn_new_ledger.setText(safe_tr("Ledger 电子表格"))
        if hasattr(self, "btn_new_lectern"):
            self.btn_new_lectern.setText(safe_tr("Lectern 演示文稿"))
        if hasattr(self, "btn_open_file"):
            self.btn_open_file.setText(safe_tr("打开本地文件..."))
        if hasattr(self, "lbl_section_nav"):
            self.lbl_section_nav.setText(safe_tr("视图"))
        if hasattr(self, "btn_nav_recent"):
            self.btn_nav_recent.setText(safe_tr("最近文档"))
        if hasattr(self, "btn_nav_templates"):
            self.btn_nav_templates.setText(safe_tr("模板库"))
        if hasattr(self, "btn_themes"):
            self.btn_themes.setText(safe_tr("主题"))
        if hasattr(self, "btn_settings"):
            self.btn_settings.setText(safe_tr("选项"))
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
