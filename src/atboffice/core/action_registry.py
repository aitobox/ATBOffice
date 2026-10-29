"""Data-driven ActionRegistry and ActionSpec command bus."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


def safe_tr(text: str) -> str:
    """Translate UI text safely for action registry."""
    return QCoreApplication.translate("ActionRegistry", text)


@dataclass
class ActionSpec:
    """Declarative specification for an application command/action."""

    id: str
    label: str
    icon: QIcon | str | None = None
    tip: str = ""
    shortcut: str | QKeySequence | QKeySequence.StandardKey | None = None
    checkable: bool = False
    checked: bool = False
    enabled: bool = True
    is_split: bool = False
    is_drop: bool = False
    handler: Callable[[], Any] | None = None


class ActionRegistry(QObject):
    """Centralized command bus and action registry.

    Provides a single source of truth for QAction instances across
    MacMenuBar, OfficeToolBar, context menus, and shortcuts.
    """

    action_triggered = Signal(str)
    action_state_changed = Signal(str, bool, bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._actions: dict[str, QAction] = {}
        self._specs: dict[str, ActionSpec] = {}

    def register_action(
        self,
        spec: ActionSpec,
        parent: QWidget | None = None,
    ) -> QAction:
        """Register an action spec and return a shared QAction instance."""
        if spec.id in self._actions:
            action = self._actions[spec.id]
            self._specs[spec.id] = spec
            self._apply_spec_to_action(action, spec)
            return action

        action_parent = parent or (self.parent() if isinstance(self.parent(), QWidget) else None)
        action = QAction(action_parent or self)
        self._apply_spec_to_action(action, spec)

        action.triggered.connect(
            lambda checked=False, aid=spec.id: self._on_action_triggered(aid)
        )
        action.toggled.connect(
            lambda chk, aid=spec.id: self.action_state_changed.emit(
                aid, action.isEnabled(), chk
            )
        )

        self._actions[spec.id] = action
        self._specs[spec.id] = spec
        return action

    def _apply_spec_to_action(self, action: QAction, spec: ActionSpec) -> None:
        """Apply properties from ActionSpec onto a QAction."""
        action.setText(spec.label)

        if spec.icon is not None:
            if isinstance(spec.icon, QIcon):
                action.setIcon(spec.icon)
            elif isinstance(spec.icon, str):
                action.setIcon(QIcon.fromTheme(spec.icon))

        if spec.tip:
            action.setToolTip(spec.tip)
            action.setStatusTip(spec.tip)

        if spec.shortcut is not None:
            if isinstance(spec.shortcut, QKeySequence):
                action.setShortcut(spec.shortcut)
            else:
                action.setShortcut(QKeySequence(spec.shortcut))

        action.setCheckable(spec.checkable)
        action.setChecked(spec.checked)
        action.setEnabled(spec.enabled)

    def register_specs(
        self,
        specs: list[ActionSpec],
        parent: QWidget | None = None,
    ) -> list[QAction]:
        """Batch register multiple action specifications."""
        return [self.register_action(spec, parent) for spec in specs]

    def get_action(self, action_id: str) -> QAction | None:
        """Retrieve the QAction associated with the given ID, if registered."""
        return self._actions.get(action_id)

    def get_spec(self, action_id: str) -> ActionSpec | None:
        """Retrieve the ActionSpec associated with the given ID, if registered."""
        return self._specs.get(action_id)

    def has_action(self, action_id: str) -> bool:
        """Check whether an action with the given ID is registered."""
        return action_id in self._actions

    def set_enabled(self, action_id: str, enabled: bool) -> None:
        """Update the enabled state of an action across all UI bindings."""
        action = self._actions.get(action_id)
        if action is not None:
            action.setEnabled(enabled)
            spec = self._specs.get(action_id)
            if spec is not None:
                spec.enabled = enabled
            self.action_state_changed.emit(action_id, enabled, action.isChecked())

    def set_checked(self, action_id: str, checked: bool) -> None:
        """Update the checked state of an action across all UI bindings."""
        action = self._actions.get(action_id)
        if action is not None:
            action.setChecked(checked)
            spec = self._specs.get(action_id)
            if spec is not None:
                spec.checked = checked
            self.action_state_changed.emit(action_id, action.isEnabled(), checked)

    def set_handler(self, action_id: str, handler: Callable[[], Any]) -> None:
        """Dynamically attach or replace the callback handler for an action."""
        spec = self._specs.get(action_id)
        if spec is not None:
            spec.handler = handler

    def trigger_action(self, action_id: str) -> bool:
        """Programmatically trigger an action if registered and enabled."""
        action = self._actions.get(action_id)
        if action is not None and action.isEnabled():
            action.trigger()
            return True
        return False

    def _on_action_triggered(self, action_id: str) -> None:
        """Internal dispatch for triggered actions, with safe fallback toast."""
        spec = self._specs.get(action_id)
        if spec is None:
            return

        if spec.handler is not None:
            try:
                spec.handler()
            except Exception:
                logger.exception("Error executing handler for action %s", action_id)
        else:
            self._show_fallback_toast(action_id)

        self.action_triggered.emit(action_id)

    def _show_fallback_toast(self, action_id: str) -> None:
        """Display a non-blocking toast on the status bar when an action has no handler."""
        win = self.parent()
        status_bar = getattr(win, "statusBar", None)
        if callable(status_bar):
            sb = status_bar()
            if sb is not None:
                message = safe_tr("功能正在联调中")
                sb.showMessage(message, 2000)
                return

        logger.info("Action %s triggered without handler (development mode)", action_id)

    def retranslate_ui(self, tr_func: Callable[[str], str] | None = None) -> None:
        """Retranslate all registered action labels and tooltips."""
        translate = tr_func or safe_tr
        for action_id, spec in self._specs.items():
            action = self._actions.get(action_id)
            if action is not None:
                action.setText(translate(spec.label))
                if spec.tip:
                    translated_tip = translate(spec.tip)
                    action.setToolTip(translated_tip)
                    action.setStatusTip(translated_tip)
