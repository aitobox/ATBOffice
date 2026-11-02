"""Unified TaskPaneDock component for Office 2003 suites (Quire, Ledger, Lectern).

Provides a standardized QDockWidget container featuring a classic Office 2003 header
(Back, Forward, Home, Title dropdown QMenu, Close button), pane registry with ID switching,
navigation history stack, and built-in standard panes (Getting Started, New Document).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import QCoreApplication, QSize, Qt, Signal
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.ui.icons import get_office_icon


def safe_tr(text: str) -> str:
    """Translate UI text safely for TaskPaneDock."""
    return QCoreApplication.translate("TaskPaneDock", text)


@dataclass
class PaneEntry:
    """Metadata and widget registration entry for a task pane."""

    pane_id: str
    title: str
    widget: QWidget
    hidden: bool = False


class TaskPaneHeader(QWidget):
    """Header toolbar containing Back, Forward, Home, Title Dropdown, and Close button."""

    back_clicked = Signal()
    forward_clicked = Signal()
    home_clicked = Signal()
    pane_selected = Signal(str)
    close_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setStyleSheet(
            """
            TaskPaneHeader {
                background-color: #ECE9D8;
                border-bottom: 1px solid #7B9EBD;
            }
            QToolButton.tp-nav {
                border: 1px solid transparent;
                background: transparent;
                border-radius: 2px;
                padding: 2px;
            }
            QToolButton.tp-nav:hover:enabled {
                background-color: #B6BDD2;
                border: 1px solid #0A246A;
            }
            QToolButton.tp-nav:disabled {
                opacity: 0.4;
            }
            QPushButton.tp-title {
                border: 1px solid transparent;
                background: transparent;
                text-align: left;
                padding-left: 4px;
                font-weight: bold;
                font-size: 11px;
                color: #000000;
            }
            QPushButton.tp-title:hover {
                background-color: #B6BDD2;
                border: 1px solid #0A246A;
            }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        # Back button
        self.btn_back = QToolButton(self)
        self.btn_back.setProperty("class", "tp-nav")
        self.btn_back.setText("◄")
        self.btn_back.setToolTip(safe_tr("后退"))
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self.back_clicked)
        layout.addWidget(self.btn_back)

        # Forward button
        self.btn_fwd = QToolButton(self)
        self.btn_fwd.setProperty("class", "tp-nav")
        self.btn_fwd.setText("►")
        self.btn_fwd.setToolTip(safe_tr("前进"))
        self.btn_fwd.setEnabled(False)
        self.btn_fwd.clicked.connect(self.forward_clicked)
        layout.addWidget(self.btn_fwd)

        # Home button
        self.btn_home = QToolButton(self)
        self.btn_home.setProperty("class", "tp-nav")
        self.btn_home.setText("🏠")
        self.btn_home.setToolTip(safe_tr("主页"))
        self.btn_home.clicked.connect(self.home_clicked)
        layout.addWidget(self.btn_home)

        # Title Dropdown button
        self.btn_title = QPushButton(self)
        self.btn_title.setProperty("class", "tp-title")
        self.btn_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.title_menu = QMenu(self.btn_title)
        self.btn_title.clicked.connect(self._show_title_menu)
        layout.addWidget(self.btn_title, stretch=1)

        # Close button
        self.btn_close = QToolButton(self)
        self.btn_close.setProperty("class", "tp-nav")
        self.btn_close.setText("✕")
        self.btn_close.setToolTip(safe_tr("关闭任务窗格"))
        self.btn_close.clicked.connect(self.close_clicked)
        layout.addWidget(self.btn_close)

        self._menu_builder: Callable[[], list[tuple[str, str, bool]]] | None = None

    def set_menu_builder(self, builder: Callable[[], list[tuple[str, str, bool]]]) -> None:
        self._menu_builder = builder

    def set_title(self, title: str) -> None:
        self.btn_title.setText(f"{title}  ▼")

    def set_nav_states(self, can_back: bool, can_fwd: bool) -> None:
        self.btn_back.setEnabled(can_back)
        self.btn_fwd.setEnabled(can_fwd)

    def _show_title_menu(self) -> None:
        if not self._menu_builder:
            return
        self.title_menu.clear()
        panes = self._menu_builder()
        for pane_id, title, is_current in panes:
            act = QAction(title, self.title_menu)
            act.setCheckable(True)
            act.setChecked(is_current)
            act.triggered.connect(lambda checked=False, pid=pane_id: self.pane_selected.emit(pid))
            self.title_menu.addAction(act)

        pos = self.btn_title.mapToGlobal(self.btn_title.rect().bottomLeft())
        self.title_menu.exec(pos)


class SectionHeader(QLabel):
    """Section header label inside a task pane."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet("font-weight: bold; color: #000080; margin-top: 8px; margin-bottom: 2px;")


class PaneLinkButton(QPushButton):
    """Clickable action link styled like an Office 2003 web-link."""

    def __init__(self, text: str, icon_key: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        if icon_key:
            self.setIcon(get_office_icon(icon_key))
            self.setIconSize(QSize(16, 16))
        self.setStyleSheet(
            """
            QPushButton {
                border: none;
                background: transparent;
                text-align: left;
                color: #003399;
                padding: 3px 2px;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #0000FF;
                text-decoration: underline;
            }
            """
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class GettingStartedPane(QWidget):
    """Office 2003 'Getting Started' task pane."""

    action_triggered = Signal(str)

    def __init__(self, app_title: str = "ATBOffice", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app_title = app_title
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # App banner
        lbl_app = QLabel(self.app_title, self)
        lbl_app.setStyleSheet("font-size: 13px; font-weight: bold; color: #333333; margin-bottom: 4px;")
        layout.addWidget(lbl_app)

        # Search Help section
        self.lbl_search = SectionHeader(safe_tr("搜索帮助:"), self)
        layout.addWidget(self.lbl_search)

        h_search = QHBoxLayout()
        self.edit_search = QLineEdit(self)
        self.edit_search.setPlaceholderText(safe_tr("输入问题或关键字"))
        self.edit_search.returnPressed.connect(self._on_search_submitted)
        h_search.addWidget(self.edit_search)

        self.btn_go = QPushButton(safe_tr("转到"), self)
        self.btn_go.setFixedWidth(46)
        self.btn_go.clicked.connect(self._on_search_submitted)
        h_search.addWidget(self.btn_go)
        layout.addLayout(h_search)

        # Open section
        self.lbl_open = SectionHeader(safe_tr("打开"), self)
        layout.addWidget(self.lbl_open)

        self.btn_more = PaneLinkButton(safe_tr("其他文档..."), "fileOpen", self)
        self.btn_more.clicked.connect(lambda: self.action_triggered.emit("open_file"))
        layout.addWidget(self.btn_more)

        self.btn_create_new = PaneLinkButton(safe_tr("创建新文档..."), "fileNew", self)
        self.btn_create_new.clicked.connect(lambda: self.action_triggered.emit("switch_new"))
        layout.addWidget(self.btn_create_new)

        # Learn section
        self.lbl_learn = SectionHeader(safe_tr("学习"), self)
        layout.addWidget(self.lbl_learn)

        self.btn_help = PaneLinkButton(safe_tr("快捷键与联机帮助"), "help", self)
        self.btn_help.clicked.connect(lambda: self.action_triggered.emit("help"))
        layout.addWidget(self.btn_help)

        layout.addStretch(1)

    def _on_search_submitted(self) -> None:
        q = self.edit_search.text().strip()
        if q:
            self.action_triggered.emit(f"search:{q}")

    def retranslate_ui(self) -> None:
        self.lbl_search.setText(safe_tr("搜索帮助:"))
        self.edit_search.setPlaceholderText(safe_tr("输入问题或关键字"))
        self.btn_go.setText(safe_tr("转到"))
        self.lbl_open.setText(safe_tr("打开"))
        self.btn_more.setText(safe_tr("其他文档..."))
        self.btn_create_new.setText(safe_tr("创建新文档..."))
        self.lbl_learn.setText(safe_tr("学习"))
        self.btn_help.setText(safe_tr("快捷键与联机帮助"))


class NewDocumentPane(QWidget):
    """Office 2003 'New Document' task pane."""

    action_triggered = Signal(str)

    def __init__(self, doc_type_name: str = "文档", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.doc_type_name = doc_type_name
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # New section
        self.lbl_new = SectionHeader(safe_tr("新建"), self)
        layout.addWidget(self.lbl_new)

        self.btn_blank = PaneLinkButton(safe_tr(f"空白{self.doc_type_name}"), "fileNew", self)
        self.btn_blank.clicked.connect(lambda: self.action_triggered.emit("new_blank"))
        layout.addWidget(self.btn_blank)

        self.btn_web = PaneLinkButton(safe_tr("网页"), "webPage", self)
        self.btn_web.clicked.connect(lambda: self.action_triggered.emit("new_web"))
        layout.addWidget(self.btn_web)

        self.btn_from_existing = PaneLinkButton(safe_tr(f"根据现有{self.doc_type_name}..."), "fileOpen", self)
        self.btn_from_existing.clicked.connect(lambda: self.action_triggered.emit("open_file"))
        layout.addWidget(self.btn_from_existing)

        # Templates section
        self.lbl_templates = SectionHeader(safe_tr("模板"), self)
        layout.addWidget(self.lbl_templates)

        self.btn_templates = PaneLinkButton(safe_tr("本机上的模板..."), "templates", self)
        self.btn_templates.clicked.connect(lambda: self.action_triggered.emit("templates"))
        layout.addWidget(self.btn_templates)

        layout.addStretch(1)

    def retranslate_ui(self) -> None:
        self.lbl_new.setText(safe_tr("新建"))
        self.btn_blank.setText(safe_tr(f"空白{self.doc_type_name}"))
        self.btn_web.setText(safe_tr("网页"))
        self.btn_from_existing.setText(safe_tr(f"根据现有{self.doc_type_name}..."))
        self.lbl_templates.setText(safe_tr("模板"))
        self.btn_templates.setText(safe_tr("本机上的模板..."))


class TaskPaneDock(QDockWidget):
    """Universal Office 2003 TaskPaneDock container widget."""

    pane_changed = Signal(str)
    action_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(safe_tr("任务窗格"), parent)
        self.setObjectName("TaskPaneDock")
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self._registry: dict[str, PaneEntry] = {}
        self._stack: list[str] = []
        self._pos: int = -1
        self._default_pane_id: str = "getting-started"

        self._container = QWidget(self)
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Header
        self.header = TaskPaneHeader(self._container)
        self.header.set_menu_builder(self._build_menu_items)
        self.header.back_clicked.connect(self.go_back)
        self.header.forward_clicked.connect(self.go_forward)
        self.header.home_clicked.connect(self.go_home)
        self.header.pane_selected.connect(self.show_pane)
        self.header.close_clicked.connect(self.hide)
        container_layout.addWidget(self.header)

        # Stacked body inside scroll area
        self.stacked_widget = QStackedWidget(self._container)
        container_layout.addWidget(self.stacked_widget, stretch=1)

        self.setWidget(self._container)
        self.setMinimumWidth(260)

        # Register default standard panes
        self._setup_default_panes()

    def _setup_default_panes(self) -> None:
        self.pane_getting_started = GettingStartedPane(parent=self)
        self.pane_getting_started.action_triggered.connect(self._handle_pane_action)
        self.register_pane("getting-started", safe_tr("开始使用"), self.pane_getting_started, is_default=True)

        self.pane_new = NewDocumentPane(parent=self)
        self.pane_new.action_triggered.connect(self._handle_pane_action)
        self.register_pane("new", safe_tr("新建"), self.pane_new)

    def _handle_pane_action(self, action: str) -> None:
        if action == "switch_new":
            self.show_pane("new")
        else:
            self.action_requested.emit(action)

    def _build_menu_items(self) -> list[tuple[str, str, bool]]:
        items: list[tuple[str, str, bool]] = []
        current = self.current_pane_id()
        for entry in self._registry.values():
            if not entry.hidden:
                items.append((entry.pane_id, entry.title, entry.pane_id == current))
        return items

    def register_pane(
        self,
        pane_id: str,
        title: str,
        widget: QWidget,
        is_default: bool = False,
        hidden: bool = False,
    ) -> None:
        """Register a pane into the dock."""
        if pane_id in self._registry:
            old = self._registry[pane_id]
            self.stacked_widget.removeWidget(old.widget)

        entry = PaneEntry(pane_id=pane_id, title=title, widget=widget, hidden=hidden)
        self._registry[pane_id] = entry
        self.stacked_widget.addWidget(widget)

        if is_default or not self._stack:
            self._default_pane_id = pane_id
            if not self._stack:
                self.show_pane(pane_id)

    def unregister_pane(self, pane_id: str) -> None:
        """Remove a pane from registration."""
        if pane_id in self._registry:
            entry = self._registry.pop(pane_id)
            self.stacked_widget.removeWidget(entry.widget)
            self._stack = [p for p in self._stack if p != pane_id]
            if self._pos >= len(self._stack):
                self._pos = len(self._stack) - 1
            if self._pos >= 0:
                self._render()

    def get_pane(self, pane_id: str) -> QWidget | None:
        """Return the widget for a registered pane ID."""
        entry = self._registry.get(pane_id)
        return entry.widget if entry else None

    def set_default_pane(self, pane_id: str) -> None:
        """Set the default home pane ID."""
        if pane_id in self._registry:
            self._default_pane_id = pane_id

    def show_pane(self, pane_id: str) -> None:
        """Display the specified pane and push onto navigation history."""
        if pane_id not in self._registry:
            return

        if self.isHidden():
            self.show()

        if not self._stack or self._stack[self._pos] != pane_id:
            self._stack = self._stack[: self._pos + 1]
            self._stack.append(pane_id)
            self._pos = len(self._stack) - 1

        self._render()

    def go_back(self) -> None:
        """Navigate back to the previous pane in history."""
        if self._pos > 0:
            self._pos -= 1
            self._render()

    def go_forward(self) -> None:
        """Navigate forward in history."""
        if self._pos < len(self._stack) - 1:
            self._pos += 1
            self._render()

    def go_home(self) -> None:
        """Navigate to the default home pane."""
        self.show_pane(self._default_pane_id)

    def current_pane_id(self) -> str:
        """Return the ID of the currently displayed pane."""
        if 0 <= self._pos < len(self._stack):
            return self._stack[self._pos]
        return ""

    def _render(self) -> None:
        pid = self.current_pane_id()
        entry = self._registry.get(pid)
        if not entry:
            return

        self.header.set_title(entry.title)
        self.header.set_nav_states(self._pos > 0, self._pos < len(self._stack) - 1)
        self.stacked_widget.setCurrentWidget(entry.widget)
        self.pane_changed.emit(pid)

    def toggle_task_pane(self, pane_id: str | None = None) -> None:
        """Toggle task pane visibility, optionally opening a specific pane."""
        if not self.isHidden():
            if pane_id and self.current_pane_id() != pane_id:
                self.show_pane(pane_id)
            else:
                self.hide()
        else:
            self.show()
            target = pane_id or (self.current_pane_id() or self._default_pane_id)
            self.show_pane(target)

    def retranslate_ui(self) -> None:
        """Update localized text across headers and default panes."""
        self.setWindowTitle(safe_tr("任务窗格"))
        if "getting-started" in self._registry:
            self._registry["getting-started"].title = safe_tr("开始使用")
            if hasattr(self.pane_getting_started, "retranslate_ui"):
                self.pane_getting_started.retranslate_ui()
        if "new" in self._registry:
            self._registry["new"].title = safe_tr("新建")
            if hasattr(self.pane_new, "retranslate_ui"):
                self.pane_new.retranslate_ui()
        self._render()
