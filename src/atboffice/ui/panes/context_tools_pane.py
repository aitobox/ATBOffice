"""Contextual task pane auto-follow (`.vibeoffice` RB.follow) for ATBOffice."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QObject, QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from atboffice.core.action_registry import ActionRegistry
from atboffice.core.i18n import safe_tr
from atboffice.core.settings import get_app_settings
from atboffice.ui.components.task_pane import SectionHeader, TaskPaneDock
from atboffice.ui.styles.luna_2003 import ui_font

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContextToolSection:
    """One labeled command section inside a contextual tools task pane."""

    title: str
    action_ids: tuple[str, ...]


@dataclass(frozen=True)
class ContextToolSet:
    """Declarative specification for one object-specific contextual tools pane."""

    set_id: str
    title: str
    sections: tuple[ContextToolSection, ...]


class ContextToolsPane(QWidget):
    """Task pane widget rendering grouped buttons backed live by ActionRegistry."""

    def __init__(
        self,
        tool_set: ContextToolSet,
        action_registry: ActionRegistry,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tool_set = tool_set
        self.action_registry = action_registry
        self._headers: list[tuple[SectionHeader, str]] = []
        self._buttons: list[tuple[QToolButton, QAction]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        self.setFont(ui_font())

        for sec in self.tool_set.sections:
            actions: list[QAction] = []
            seen_ids: set[str] = set()
            for aid in sec.action_ids:
                if aid in seen_ids:
                    continue
                act = self.action_registry.get_action(aid)
                if act is not None:
                    seen_ids.add(aid)
                    actions.append(act)
            if not actions:
                continue

            hdr = SectionHeader(safe_tr(sec.title), self)
            hdr.setFont(ui_font(9, bold=True))
            layout.addWidget(hdr)
            self._headers.append((hdr, sec.title))

            for act in actions:
                btn = QToolButton(self)
                btn.setDefaultAction(act)
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                btn.setAutoRaise(True)
                btn.setIconSize(QSize(16, 16))
                btn.setFixedHeight(26)
                btn.setFont(ui_font())
                btn.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed,
                )
                layout.addWidget(btn)
                self._buttons.append((btn, act))

        layout.addStretch(1)

    def refresh_actions(self) -> None:
        """Synchronize button visibility with action availability without duplicating logic."""
        for btn, act in self._buttons:
            btn.setVisible(act.isVisible())

    def retranslate_ui(self) -> None:
        """Update localized section headings after a language change."""
        for hdr, title_src in self._headers:
            hdr.setText(safe_tr(title_src))


class TaskPaneFollowController(QObject):
    """Switch the open TaskPaneDock to match the selected object and restore on deselect."""

    def __init__(
        self,
        window: QMainWindow,
        task_pane_dock: TaskPaneDock,
        action_registry: ActionRegistry,
        sets: list[ContextToolSet],
        pane_aliases: dict[str, str] | None = None,
        min_window_width: int = 820,
        setting_key: str = "view/pane_follows_selection",
    ) -> None:
        super().__init__(window)
        self.window = window
        self.task_pane_dock = task_pane_dock
        self.action_registry = action_registry
        self._sets: dict[str, ContextToolSet] = {s.set_id: s for s in sets}
        self._pane_aliases: dict[str, str] = dict(pane_aliases or {})
        self._min_window_width = min_window_width
        self._setting_key = setting_key

        self._panes: dict[str, tuple[ContextToolSet, ContextToolsPane]] = {}
        self._ours: set[str] = set(self._pane_aliases.values())
        self._active_context: str | None = None
        self._before_pane_id: str | None = None

        for tool_set in sets:
            pane_id = f"tools-{tool_set.set_id}"
            pane = ContextToolsPane(tool_set, action_registry, parent=task_pane_dock)
            task_pane_dock.register_pane(pane_id, safe_tr(tool_set.title), pane, hidden=True)
            self._panes[pane_id] = (tool_set, pane)
            self._ours.add(pane_id)

        cur = task_pane_dock.current_pane_id()
        if cur and cur not in self._ours:
            self._before_pane_id = cur
        task_pane_dock.pane_changed.connect(self._on_dock_pane_changed)

    def _is_enabled(self) -> bool:
        try:
            return bool(get_app_settings().get_value(self._setting_key, True))
        except Exception:
            logger.debug("Failed to read setting %s", self._setting_key, exc_info=True)
            return True

    def _on_dock_pane_changed(self, pane_id: str) -> None:
        if pane_id and pane_id not in self._ours:
            self._before_pane_id = pane_id

    def _resolve_target_pane(self, context_kind: str | None) -> str | None:
        if not context_kind:
            return None
        if context_kind in self._pane_aliases:
            target = self._pane_aliases[context_kind]
            return target if self.task_pane_dock.get_pane(target) is not None else None
        cand = f"tools-{context_kind}"
        return cand if cand in self._panes else None

    def sync_context(self, context_kind: str | None) -> None:
        """Follow ``context_kind`` if the dock is open, window is wide enough, and enabled."""
        target = self._resolve_target_pane(context_kind)
        if not self._is_enabled():
            return
        if self.task_pane_dock.isHidden():
            return
        if self.window.width() < self._min_window_width:
            return

        cur = self.task_pane_dock.current_pane_id()
        self._active_context = context_kind if target else None

        if target:
            if target in self._panes:
                self._panes[target][1].refresh_actions()
            if cur == target:
                return
            if cur and cur not in self._ours:
                self._before_pane_id = cur
            self.task_pane_dock.show_pane(target)
            return

        if cur in self._ours:
            restore = self._before_pane_id
            if (
                restore
                and restore not in self._ours
                and self.task_pane_dock.get_pane(restore) is not None
            ):
                self.task_pane_dock.show_pane(restore)
            else:
                default_id = getattr(self.task_pane_dock, "_default_pane_id", "getting-started")
                if default_id and self.task_pane_dock.get_pane(default_id) is not None:
                    self.task_pane_dock.show_pane(default_id)

    def refresh_action_states(self) -> None:
        """Refresh action visibility inside all contextual tool panes."""
        for _spec, pane in self._panes.values():
            pane.refresh_actions()

    def retranslate_ui(self) -> None:
        """Retranslate contextual pane titles and headings."""
        registry = getattr(self.task_pane_dock, "_registry", {})
        for pane_id, (tool_set, pane) in self._panes.items():
            if pane_id in registry:
                registry[pane_id].title = safe_tr(tool_set.title)
            pane.retranslate_ui()
        if self.task_pane_dock.current_pane_id() in self._panes:
            self.task_pane_dock._render()
