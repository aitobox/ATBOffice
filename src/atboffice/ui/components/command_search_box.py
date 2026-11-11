"""Global Command Search ('Tell me what you want to do' / Search Commands).

Mounted at the top right of the main menu bar across Quire, Ledger, and Lectern.
Provides real-time fuzzy & synonym search across ActionRegistry with keyboard
navigation (Up/Down/Enter/Esc) and direct action execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt, Signal
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.action_registry import ActionRegistry
from atboffice.ui.icons import get_office_icon

if TYPE_CHECKING:
    pass


def safe_tr(text: str) -> str:
    """Translate UI text safely for CommandSearchBox."""
    return QCoreApplication.translate("CommandSearchBox", text)


# Bilingual synonym map aligned with .vibeoffice/public/common/search.js
SYNONYMS: dict[str, list[str]] = {
    # File & Save
    "save": ["保存", "另存为", "save", "save_as"],
    "保存": ["save", "save_as", "另存为"],
    "open": ["打开", "open", "file_open"],
    "打开": ["open", "file_open"],
    "print": ["打印", "打印预览", "页面设置", "print", "print_preview", "page_setup"],
    "打印": ["print", "print_preview", "page_setup", "页面设置"],
    "close": ["关闭", "退出", "close", "exit"],
    "关闭": ["close", "exit"],
    # Edit & Clipboard
    "copy": ["复制", "copy"],
    "复制": ["copy"],
    "cut": ["剪切", "cut"],
    "剪切": ["cut"],
    "paste": ["粘贴", "选择性粘贴", "paste", "paste_special"],
    "粘贴": ["paste", "paste_special"],
    "clipboard": ["剪贴板", "clipboard", "taskpane_clipboard", "taskpane"],
    "剪贴板": ["clipboard", "taskpane_clipboard", "taskpane"],
    "undo": ["撤销", "undo"],
    "撤销": ["undo"],
    "redo": ["重做", "恢复", "redo"],
    "重做": ["redo"],
    "find": ["查找", "find", "search"],
    "查找": ["find", "search"],
    "replace": ["替换", "replace"],
    "替换": ["replace"],
    "select": ["全选", "选择", "select_all"],
    "全选": ["select_all", "select"],
    # Formatting
    "bold": ["加粗", "粗体", "bold"],
    "加粗": ["bold"],
    "italic": ["斜体", "italic"],
    "斜体": ["italic"],
    "underline": ["下划线", "underline"],
    "下划线": ["underline"],
    "font": ["字体", "字号", "font", "font_size", "format_font"],
    "字体": ["font", "format_font", "font_size"],
    "color": ["颜色", "字体颜色", "填充颜色", "color", "font_color", "fill_color"],
    "颜色": ["color", "font_color", "fill_color"],
    "align": ["对齐", "居中", "左对齐", "右对齐", "align_center", "align_left"],
    "对齐": ["align", "align_center", "align_left", "align_right"],
    # Insert & Objects
    "table": ["表格", "插入表格", "table", "insert_table"],
    "表格": ["table", "insert_table"],
    "picture": ["图片", "图像", "picture", "image", "insert_picture"],
    "图片": ["picture", "image", "insert_picture"],
    "image": ["picture", "image", "图片"],
    "chart": ["图表", "chart", "insert_chart"],
    "图表": ["chart", "insert_chart"],
    "hyperlink": ["超链接", "链接", "hyperlink", "link"],
    "链接": ["hyperlink", "link"],
    "symbol": ["符号", "特殊符号", "symbol"],
    "符号": ["symbol"],
    # Tools & Calculations
    "sum": ["求和", "自动求和", "sum", "autosum"],
    "求和": ["sum", "autosum"],
    "sort": ["排序", "升序", "降序", "sort"],
    "排序": ["sort", "sort_asc", "sort_desc"],
    "filter": ["筛选", "自动筛选", "filter", "autofilter"],
    "筛选": ["filter", "autofilter"],
    "smartart": ["智能图示", "smartart", "intelliart"],
    "智能图示": ["smartart", "intelliart"],
    "slideshow": ["幻灯片放映", "放映", "slide_show", "presentation"],
    "放映": ["slide_show", "presentation"],
    "options": ["选项", "设置", "首选项", "options", "preferences"],
    "选项": ["options", "preferences"],
    "help": ["帮助", "关于", "help", "about"],
    "帮助": ["help", "about"],
}


@dataclass
class CommandSearchResult:
    """Represents a matched command ready for display and execution."""

    action_id: str
    label: str
    tip: str = ""
    shortcut: str = ""
    icon: QIcon | None = None
    enabled: bool = True
    score: float = 0.0


class CommandSearchPopup(QFrame):
    """Floating dropdown list displaying search results with keyboard navigation."""

    action_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            """
            CommandSearchPopup {
                background-color: #FFFFFF;
                border: 1px solid #7B9EBD;
                border-radius: 3px;
            }
            QListWidget {
                border: none;
                background: transparent;
                outline: none;
            }
            QListWidget::item {
                padding: 4px 6px;
                border-bottom: 1px solid #F0F0F0;
                color: #222222;
                font-size: 11px;
            }
            QListWidget::item:selected {
                background-color: #B6BDD2;
                color: #000000;
            }
            QListWidget::item:hover:!selected {
                background-color: #F2F5FB;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        self.list_widget = QListWidget(self)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        self._results: list[CommandSearchResult] = []

    def set_results(self, results: list[CommandSearchResult]) -> None:
        self._results = results
        self.list_widget.clear()

        if not results:
            item = QListWidgetItem(safe_tr("没有找到匹配的命令"), self.list_widget)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(Qt.GlobalColor.gray)
            self.setFixedHeight(36)
            return

        for res in results:
            text = res.label
            if res.shortcut:
                text = f"{res.label:<30}  [{res.shortcut}]"
            item = QListWidgetItem(text, self.list_widget)
            if res.icon is not None and not res.icon.isNull():
                item.setIcon(res.icon)
            if not res.enabled:
                item.setForeground(Qt.GlobalColor.gray)
            if res.tip:
                item.setToolTip(res.tip)
            item.setData(Qt.ItemDataRole.UserRole, res.action_id)

        self.list_widget.setCurrentRow(0)
        item_height = 28
        total_height = min(len(results) * item_height + 4, 300)
        self.setFixedHeight(total_height)

    def select_next(self) -> None:
        row = self.list_widget.currentRow()
        if row < self.list_widget.count() - 1:
            self.list_widget.setCurrentRow(row + 1)

    def select_prev(self) -> None:
        row = self.list_widget.currentRow()
        if row > 0:
            self.list_widget.setCurrentRow(row - 1)

    def execute_current(self) -> bool:
        row = self.list_widget.currentRow()
        if row >= 0 and row < len(self._results):
            res = self._results[row]
            if res.enabled:
                self.hide()
                self.action_selected.emit(res.action_id)
                return True
        return False

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        action_id = item.data(Qt.ItemDataRole.UserRole)
        if action_id:
            self.hide()
            self.action_selected.emit(action_id)


class CommandSearchBox(QWidget):
    """Tell Me / Command Search Box mounted on main menu bar corner."""

    action_executed = Signal(str)

    def __init__(
        self,
        action_registry: ActionRegistry | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.action_registry: ActionRegistry | None = action_registry
        self.setFixedWidth(210)
        self.setFixedHeight(24)

        self._init_ui()
        self._setup_shortcuts()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 1, 4, 1)
        layout.setSpacing(2)

        # Search line edit
        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText(safe_tr("请告诉我您想要做什么..."))
        self.line_edit.setStyleSheet(
            """
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #7B9EBD;
                border-radius: 2px;
                padding: 1px 4px 1px 20px;
                font-size: 11px;
                color: #000000;
            }
            QLineEdit:focus {
                border: 1px solid #0A246A;
                background-color: #FFFFFA;
            }
            """
        )

        # Magnifier icon button inside line edit
        self.icon_btn = QToolButton(self.line_edit)
        self.icon_btn.setIcon(get_office_icon("find"))
        self.icon_btn.setFixedSize(16, 16)
        self.icon_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.icon_btn.setStyleSheet("border: none; background: transparent;")
        self.icon_btn.move(3, 3)

        self.line_edit.textChanged.connect(self._on_text_changed)
        self.line_edit.returnPressed.connect(self._on_return_pressed)
        self.line_edit.installEventFilter(self)

        layout.addWidget(self.line_edit)

        # Floating popup
        self.popup = CommandSearchPopup(self)
        self.popup.action_selected.connect(self.execute_action)

    def _setup_shortcuts(self) -> None:
        # Alt+Q to focus Tell Me search box
        self.shortcut_focus = QShortcut(QKeySequence("Alt+Q"), self)
        self.shortcut_focus.activated.connect(self.focus_and_select_all)

    def focus_and_select_all(self) -> None:
        """Set focus to input and select current query text."""
        self.line_edit.setFocus()
        self.line_edit.selectAll()

    def set_action_registry(self, registry: ActionRegistry) -> None:
        """Attach or update the central ActionRegistry."""
        self.action_registry = registry

    def _on_text_changed(self, text: str) -> None:
        q = text.strip()
        if not q:
            self.popup.hide()
            return
        results = self.search_commands(q)
        self.popup.set_results(results)
        self._position_popup()
        self.popup.show()

    def _position_popup(self) -> None:
        """Position the dropdown popup directly underneath the search box."""
        pos = self.line_edit.mapToGlobal(QPoint(0, self.line_edit.height() + 1))
        self.popup.move(pos)
        self.popup.setFixedWidth(max(self.line_edit.width(), 260))

    def _on_return_pressed(self) -> None:
        if self.popup.isVisible():
            if self.popup.execute_current():
                return
        # If popup not visible or not executed, try direct search match
        q = self.line_edit.text().strip()
        if q:
            results = self.search_commands(q)
            if results and results[0].enabled:
                self.execute_action(results[0].action_id)

    def execute_action(self, action_id: str) -> None:
        """Trigger selected action via ActionRegistry and reset search state."""
        self.popup.hide()
        self.line_edit.clear()
        self.line_edit.clearFocus()

        if self.action_registry is not None:
            self.action_registry.trigger_action(action_id)
        self.action_executed.emit(action_id)

    def search_commands(self, query: str) -> list[CommandSearchResult]:
        """Perform fuzzy & synonym search over all registered actions."""
        if not self.action_registry:
            return []

        q = query.lower().strip()
        tokens = [t for t in re.split(r"\s+", q) if t]
        if not tokens:
            return []

        # Find synonyms for query tokens
        syn_words: set[str] = set()
        for tok in tokens:
            if tok in SYNONYMS:
                syn_words.update(w.lower() for w in SYNONYMS[tok])
            for key, val in SYNONYMS.items():
                if tok in key.lower() or any(tok in v.lower() for v in val):
                    syn_words.add(key.lower())
                    syn_words.update(v.lower() for v in val)

        results: list[CommandSearchResult] = []
        specs = getattr(self.action_registry, "_specs", {})
        actions = getattr(self.action_registry, "_actions", {})

        for aid, spec in specs.items():
            label = spec.label or ""
            tip = spec.tip or ""
            action = actions.get(aid)
            enabled = action.isEnabled() if action is not None else spec.enabled

            shortcut_str = ""
            if spec.shortcut is not None:
                shortcut_str = (
                    spec.shortcut.toString()
                    if hasattr(spec.shortcut, "toString")
                    else str(spec.shortcut)
                )

            lbl_lower = label.lower()
            aid_lower = aid.lower()
            tip_lower = tip.lower()

            score = 0.0

            # 1. Exact match on label or action_id
            if q == lbl_lower or q == aid_lower:
                score += 10.0
            # 2. Prefix match on label
            elif lbl_lower.startswith(q) or aid_lower.startswith(q):
                score += 8.0
            # 3. Substring match on label
            elif q in lbl_lower:
                score += 6.0
            # 4. Synonym match
            elif any(syn in lbl_lower or syn in aid_lower for syn in syn_words):
                score += 5.0
            # 5. Token match across label, tip, shortcut
            else:
                match_count = 0
                for tok in tokens:
                    if tok in lbl_lower or tok in aid_lower or tok in tip_lower:
                        match_count += 1
                if match_count == len(tokens):
                    score += 4.0
                elif match_count > 0:
                    score += 2.0 * (match_count / len(tokens))

            if score > 0:
                icon = spec.icon if isinstance(spec.icon, QIcon) else None
                if icon is None and action is not None:
                    icon = action.icon()

                results.append(
                    CommandSearchResult(
                        action_id=aid,
                        label=label,
                        tip=tip,
                        shortcut=shortcut_str,
                        icon=icon,
                        enabled=enabled,
                        score=score,
                    )
                )

        results.sort(key=lambda x: (not x.enabled, -x.score, len(x.label)))
        return results[:10]

    def eventFilter(self, obj: Any, event: QEvent) -> bool:
        if obj == self.line_edit and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down:
                if self.popup.isVisible():
                    self.popup.select_next()
                    return True
                else:
                    self._on_text_changed(self.line_edit.text())
                    return True
            elif key == Qt.Key.Key_Up:
                if self.popup.isVisible():
                    self.popup.select_prev()
                    return True
            elif key == Qt.Key.Key_Escape:
                if self.popup.isVisible():
                    self.popup.hide()
                    return True
                self.line_edit.clear()
                self.line_edit.clearFocus()
                return True
        return super().eventFilter(obj, event)

    def retranslate_ui(self) -> None:
        """Update localized placeholder text and labels."""
        self.line_edit.setPlaceholderText(safe_tr("请告诉我您想要做什么..."))
        self.icon_btn.setToolTip(safe_tr("搜索命令 (Alt+Q)"))
