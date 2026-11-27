"""Declarative lazy Paper 2016 Ribbon engine for ATBOffice editors.

Provides a strictly lazy Ribbon chrome over ``ActionRegistry`` commands,
corresponding to ``.vibeoffice/public/common/ribbon.js``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeyEvent, QKeySequence, QResizeEvent, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.action_registry import ActionRegistry
from atboffice.core.fault_guard import is_alive
from atboffice.core.i18n import safe_tr, source_to_english
from atboffice.core.settings import get_app_settings
from atboffice.ui.icons import get_office_icon, has_office_icon
from atboffice.ui.styles.luna_2003 import theme_tokens, ui_font

logger = logging.getLogger(__name__)

_AMP_RE = re.compile(r"(?<!&)&(?!&)")
_ASIAN_MNEMONIC_RE = re.compile(r"\s*\(&[A-Za-z0-9]\)")
_ACCESS_KEY_RE = re.compile(r"(?:\(&([A-Za-z0-9])\)|(?<!&)&([A-Za-z0-9]))")


def _clean_ribbon_label(text: str) -> str:
    """Strip mnemonic accelerators and trailing ellipsis for compact Ribbon labels."""
    cleaned = _ASIAN_MNEMONIC_RE.sub("", text)
    cleaned = _AMP_RE.sub("", cleaned).replace("&&", "&")
    cleaned = re.sub(r"(\.\.\.|…)$", "", cleaned.strip())
    return cleaned.strip()


def _extract_access_key(text: str) -> str | None:
    """Extract single-character mnemonic key if present in ``text``."""
    m = _ACCESS_KEY_RE.search(text)
    if not m:
        return None
    ch = m.group(1) or m.group(2)
    return ch.upper() if ch else None


@dataclass(frozen=True)
class RibbonItemSpec:
    """Declarative specification for one command, row, dropdown, or widget inside a group."""

    cmd: str | None = None
    size: str = "medium"  # "large" | "medium" | "small"
    label: str | None = None
    icon: str | None = None
    row: tuple[RibbonItemSpec | str, ...] | None = None
    split: bool = False
    drop: bool = False
    menu_builder: Callable[[], QMenu] | None = None
    widget_factory: Callable[[QWidget], QWidget] | None = None


@dataclass(frozen=True)
class RibbonGroupSpec:
    """Declarative specification for a labeled group of Ribbon items."""

    label: str
    items: tuple[RibbonItemSpec | str, ...]
    launcher: str | None = None
    icon: str | None = None


@dataclass(frozen=True)
class RibbonTabSpec:
    """Declarative specification for a single Ribbon tab."""

    tab_id: str
    label: str
    groups: tuple[RibbonGroupSpec, ...]


@dataclass(frozen=True)
class RibbonContextSetSpec:
    """Declarative specification for a contextual tab set driven by live selection."""

    set_id: str
    set_label: str
    when: Callable[[], bool]
    tabs: tuple[RibbonTabSpec, ...]
    auto_open: bool = False
    accent: str = "#008080"


@dataclass(frozen=True)
class RibbonSpec:
    """Complete declarative Ribbon layout for one editor application."""

    app_id: str
    qat: tuple[RibbonItemSpec | str, ...]
    file_actions: tuple[str, ...]
    tabs: tuple[RibbonTabSpec, ...]
    contextual: tuple[RibbonContextSetSpec, ...] = ()
    icons: dict[str, str] = field(default_factory=dict)


class _FoldPopup(QFrame):
    """Popup frame hosting a folded RibbonGroupWidget's controls."""

    def __init__(self, on_close: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self._on_close = on_close
        self.setObjectName("RibbonFoldPopup")
        tok = theme_tokens("paper2016")
        self.setStyleSheet(
            f"QFrame#RibbonFoldPopup {{ background: #FFFFFF; border: 1px solid {tok.tb_border}; "
            "border-radius: 3px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

    def hideEvent(self, event: Any) -> None:
        super().hideEvent(event)
        self._on_close()


class RibbonGroupWidget(QWidget):
    """Renders columns, optional dialog launcher, and narrow-window fold for one RibbonGroupSpec."""

    def __init__(
        self,
        group_spec: RibbonGroupSpec,
        action_registry: ActionRegistry,
        icon_resolver: Callable[[str | None, str | None, int], QIcon],
        on_command_executed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.group_spec = group_spec
        self.action_registry = action_registry
        self._resolve_icon = icon_resolver
        self._on_command_executed = on_command_executed
        self._is_folded = False
        self._fold_popup: _FoldPopup | None = None

        self._bound_buttons: list[tuple[QToolButton, QAction | None, RibbonItemSpec, QIcon]] = []
        self._action_targets: list[tuple[QWidget, str, str | None]] = []

        self.setObjectName("RibbonGroupWidget")
        self.setFont(ui_font())

        outer = QHBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 2)
        outer.setSpacing(4)

        self._content_col = QWidget(self)
        self._content_layout = QVBoxLayout(self._content_col)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(2)

        self._body_widget = QWidget(self._content_col)
        self._body_layout = QHBoxLayout(self._body_widget)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(4)
        self._build_columns()
        self._content_layout.addWidget(self._body_widget, 1)

        # Folded placeholder button (hidden until set_folded(True))
        self._fold_btn = QToolButton(self._content_col)
        self._fold_btn.setObjectName("RibbonGroupFoldButton")
        self._fold_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._fold_btn.setIconSize(QSize(32, 32))
        self._fold_btn.setAutoRaise(True)
        self._fold_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._fold_btn.setFont(ui_font(8.5))
        self._fold_btn.setIcon(self._resolve_fold_icon())
        self._fold_btn.clicked.connect(self._toggle_fold_popup)
        self._fold_btn.hide()
        self._content_layout.addWidget(self._fold_btn, 1)

        # Bottom label + optional dialog launcher
        self._label_bar = QWidget(self._content_col)
        label_layout = QHBoxLayout(self._label_bar)
        label_layout.setContentsMargins(2, 0, 2, 0)
        label_layout.setSpacing(2)

        self._label_lbl = QLabel(safe_tr(group_spec.label), self._label_bar)
        self._label_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label_lbl.setFont(ui_font(8))
        self._label_lbl.setStyleSheet("color: #666058; background: transparent;")
        label_layout.addWidget(self._label_lbl, 1)

        self._launcher_btn: QToolButton | None = None
        if group_spec.launcher:
            launch_act = self.action_registry.get_action(group_spec.launcher)
            lbtn = QToolButton(self._label_bar)
            lbtn.setObjectName("RibbonLauncherButton")
            lbtn.setAutoRaise(True)
            lbtn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            lbtn.setFixedSize(15, 15)
            lbtn.setText("↗")
            lbtn.setFont(ui_font(8))
            if launch_act is not None:
                lbtn.setToolTip(_clean_ribbon_label(launch_act.text()))
                lbtn.clicked.connect(lambda _chk=False, a=launch_act: a.trigger())
                self._action_targets.append((lbtn, _clean_ribbon_label(launch_act.text()), None))
            else:
                lbtn.setVisible(False)
            label_layout.addWidget(lbtn, 0, Qt.AlignmentFlag.AlignRight)
            self._launcher_btn = lbtn

        self._content_layout.addWidget(self._label_bar, 0)
        outer.addWidget(self._content_col)

        # Vertical group divider
        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #D8D2C6; border: none;")
        outer.addWidget(sep)

        self.retranslate_ui()

    @property
    def is_folded(self) -> bool:
        """Return whether this group is currently folded to a single drop button."""
        return self._is_folded

    def _resolve_fold_icon(self) -> QIcon:
        if self.group_spec.icon:
            ico = self._resolve_icon(None, self.group_spec.icon, 32)
            if not ico.isNull():
                return ico
        for raw in self.group_spec.items:
            if isinstance(raw, str):
                if raw != "|":
                    ico = self._resolve_icon(raw, None, 32)
                    if not ico.isNull():
                        return ico
            elif raw.row:
                for sub in raw.row:
                    cmd = sub if isinstance(sub, str) else sub.cmd
                    ovr = None if isinstance(sub, str) else sub.icon
                    if cmd and cmd != "|":
                        ico = self._resolve_icon(cmd, ovr, 32)
                        if not ico.isNull():
                            return ico
            else:
                ico = self._resolve_icon(raw.cmd, raw.icon, 32)
                if not ico.isNull():
                    return ico
        return get_office_icon("app", size=32)

    def _normalize_item(
        self, raw: RibbonItemSpec | str, default_size: str = "medium"
    ) -> RibbonItemSpec:
        if isinstance(raw, str):
            return RibbonItemSpec(cmd=raw, size=default_size)
        return raw

    def _build_columns(self) -> None:
        col_widget: QWidget | None = None
        col_layout: QVBoxLayout | None = None
        col_kind: str = ""
        col_count = 0

        for raw in self.group_spec.items:
            if raw == "|":
                col_widget = None
                col_layout = None
                col_kind = ""
                col_count = 0
                continue

            item = self._normalize_item(raw)
            if item.row is not None:
                row_w = self._build_row_widget(item.row)
                if col_layout is None or col_kind != "rows" or col_count >= 2:
                    col_widget = QWidget(self._body_widget)
                    col_layout = QVBoxLayout(col_widget)
                    col_layout.setContentsMargins(0, 0, 0, 0)
                    col_layout.setSpacing(2)
                    self._body_layout.addWidget(col_widget, 0, Qt.AlignmentFlag.AlignTop)
                    col_kind = "rows"
                    col_count = 0
                col_layout.addWidget(row_w)
                col_count += 1
                continue

            widget = self._build_item_widget(item)
            if item.size == "large":
                self._body_layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
                col_widget = None
                col_layout = None
                col_kind = ""
                col_count = 0
            else:
                if col_layout is None or col_kind != "stack" or col_count >= 3:
                    col_widget = QWidget(self._body_widget)
                    col_layout = QVBoxLayout(col_widget)
                    col_layout.setContentsMargins(0, 0, 0, 0)
                    col_layout.setSpacing(1)
                    self._body_layout.addWidget(col_widget, 0, Qt.AlignmentFlag.AlignTop)
                    col_kind = "stack"
                    col_count = 0
                col_layout.addWidget(widget)
                col_count += 1

    def _build_row_widget(self, row_items: tuple[RibbonItemSpec | str, ...]) -> QWidget:
        row_w = QWidget(self._body_widget)
        row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(2)
        for sub in row_items:
            if sub == "|":
                sep = QFrame(row_w)
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setFixedWidth(1)
                sep.setFixedHeight(16)
                sep.setStyleSheet("background: #D8D2C6; border: none;")
                row_l.addWidget(sep)
                continue
            if isinstance(sub, str):
                item = RibbonItemSpec(cmd=sub, size="small")
            else:
                if sub.size == "medium" and sub.label is None and sub.widget_factory is None:
                    item = RibbonItemSpec(
                        cmd=sub.cmd,
                        size="small",
                        label=sub.label,
                        icon=sub.icon,
                        row=sub.row,
                        split=sub.split,
                        drop=sub.drop,
                        menu_builder=sub.menu_builder,
                        widget_factory=sub.widget_factory,
                    )
                else:
                    item = sub
            row_l.addWidget(self._build_item_widget(item))
        row_l.addStretch(1)
        return row_w

    def _build_item_widget(self, item: RibbonItemSpec) -> QWidget:
        if item.widget_factory is not None:
            w = item.widget_factory(self._body_widget)
            if isinstance(w, QComboBox):
                self._action_targets.append((w, w.toolTip() or "Combo", None))
            return w

        btn = QToolButton(self._body_widget)
        btn.setAutoRaise(True)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFont(ui_font(8.5))

        is_large = item.size == "large"
        icon_px = 32 if is_large else 16
        btn.setIconSize(QSize(icon_px, icon_px))

        if is_large:
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setMinimumHeight(58)
            btn.setMinimumWidth(42)
            btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        elif item.size == "small":
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            btn.setFixedHeight(22)
        else:
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setFixedHeight(20)

        action: QAction | None = None
        fallback_icon = self._resolve_icon(item.cmd, item.icon, icon_px)

        if item.cmd:
            action = self.action_registry.get_action(item.cmd)
            if action is not None:
                btn.setDefaultAction(action)
                if item.drop:
                    btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                elif item.split:
                    btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

                if item.menu_builder is not None:
                    menu = item.menu_builder()
                    if menu is not None:
                        btn.setMenu(menu)
                elif action.menu() is not None:
                    btn.setMenu(action.menu())

                action.changed.connect(
                    lambda b=btn, a=action, it=item, fi=fallback_icon: self._sync_button(
                        b, a, it, fi
                    )
                )

        if action is None:
            if item.drop or item.menu_builder is not None:
                btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                if item.menu_builder is not None:
                    menu = item.menu_builder()
                    if menu is not None:
                        btn.setMenu(menu)
            if not fallback_icon.isNull():
                btn.setIcon(fallback_icon)

        if not item.drop and item.menu_builder is None and self._on_command_executed is not None:
            btn.clicked.connect(lambda _chk=False: self._on_command_executed())

        self._sync_button(btn, action, item, fallback_icon)
        self._bound_buttons.append((btn, action, item, fallback_icon))

        src_label = item.label or (action.text() if action is not None else item.cmd or "")
        en_label = source_to_english(src_label) if src_label else None
        self._action_targets.append((btn, _clean_ribbon_label(safe_tr(src_label)), en_label))
        return btn

    def _sync_button(
        self,
        btn: QToolButton,
        action: QAction | None,
        item: RibbonItemSpec,
        fallback_icon: QIcon,
    ) -> None:
        if not is_alive(btn):
            return
        if item.size == "small":
            btn.setText("")
            tip = safe_tr(item.label) if item.label else (action.text() if action else "")
            btn.setToolTip(_clean_ribbon_label(tip))
        else:
            raw_lbl = safe_tr(item.label) if item.label else (action.text() if action else "")
            cleaned = _clean_ribbon_label(raw_lbl)
            if btn.text() != cleaned:
                btn.setText(cleaned)
            tip = (action.toolTip() if action and action.toolTip() else cleaned) or cleaned
            btn.setToolTip(tip)

        if (action is None or action.icon().isNull()) and not fallback_icon.isNull():
            if btn.icon().isNull():
                btn.setIcon(fallback_icon)

    def set_folded(self, folded: bool) -> None:
        """Fold or unfold this group for narrow viewports."""
        if self._is_folded == folded:
            return
        self._is_folded = folded
        if not folded:
            self._close_fold_popup()
            self._fold_btn.hide()
            self._body_widget.show()
            self._label_bar.show()
        else:
            self._body_widget.hide()
            self._label_bar.hide()
            self._fold_btn.show()

    def _toggle_fold_popup(self) -> None:
        if self._fold_popup is not None and self._fold_popup.isVisible():
            self._close_fold_popup()
            return
        self._open_fold_popup()

    def _open_fold_popup(self) -> None:
        self._close_fold_popup()
        pop = _FoldPopup(self._restore_from_popup, parent=self)
        pop_layout = pop.layout()
        assert pop_layout is not None
        self._content_layout.removeWidget(self._body_widget)
        self._content_layout.removeWidget(self._label_bar)
        pop_layout.addWidget(self._body_widget)
        pop_layout.addWidget(self._label_bar)
        self._body_widget.show()
        self._label_bar.show()
        pos = self._fold_btn.mapToGlobal(QPoint(0, self._fold_btn.height()))
        pop.move(pos)
        pop.show()
        self._fold_popup = pop

    def _restore_from_popup(self) -> None:
        if not is_alive(self) or not is_alive(self._body_widget):
            return
        if self._fold_popup is not None:
            pop_layout = self._fold_popup.layout()
            if pop_layout is not None:
                pop_layout.removeWidget(self._body_widget)
                pop_layout.removeWidget(self._label_bar)
        self._content_layout.insertWidget(0, self._body_widget, 1)
        self._content_layout.addWidget(self._label_bar, 0)
        if self._is_folded:
            self._body_widget.hide()
            self._label_bar.hide()
        self._fold_popup = None

    def _close_fold_popup(self) -> None:
        if self._fold_popup is not None:
            pop = self._fold_popup
            self._fold_popup = None
            if is_alive(pop):
                pop.close()
                pop.deleteLater()
            self._restore_from_popup()

    def keytip_targets(self) -> list[tuple[QWidget, str, str | None]]:
        """Return interactive widgets in this group for KeyTips assignment."""
        targets: list[tuple[QWidget, str, str | None]] = []
        if self._is_folded:
            targets.append(
                (
                    self._fold_btn,
                    _clean_ribbon_label(safe_tr(self.group_spec.label)),
                    source_to_english(self.group_spec.label),
                )
            )
            return targets
        for w, _lbl, en in self._action_targets:
            if is_alive(w) and w.isVisible():
                lbl = w.text() if isinstance(w, QToolButton) and w.text() else w.toolTip()
                targets.append((w, lbl or _lbl, en))
        return targets

    def retranslate_ui(self) -> None:
        """Refresh localized group label, fold text, launcher tooltip, and button texts."""
        grp_lbl = safe_tr(self.group_spec.label)
        self._label_lbl.setText(grp_lbl)
        self._fold_btn.setText(f"{grp_lbl} ▾")
        self._fold_btn.setToolTip(grp_lbl)
        if self._launcher_btn is not None and self.group_spec.launcher:
            act = self.action_registry.get_action(self.group_spec.launcher)
            if act is not None:
                self._launcher_btn.setToolTip(_clean_ribbon_label(act.text()))
        for btn, action, item, fallback_icon in self._bound_buttons:
            self._sync_button(btn, action, item, fallback_icon)


class RibbonBar(QWidget):
    """Paper 2016 tabbed Ribbon host with QAT, File menu, lazy tab panels, and KeyTips."""

    def __init__(
        self,
        spec: RibbonSpec,
        action_registry: ActionRegistry,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self.action_registry = action_registry

        self._current_tab_id: str = spec.tabs[0].tab_id if spec.tabs else ""
        self._back_tab_id: str | None = None
        self._active_ctx_ids: tuple[str, ...] = ()
        self._collapsed: bool = bool(
            get_app_settings().get_value(f"ui/ribbon_collapsed_{spec.app_id}", False)
        )
        self._peeking: bool = False

        self._tab_panels: dict[str, QWidget] = {}
        self._tab_buttons: dict[str, QToolButton] = {}
        self._qat_buttons: list[tuple[QToolButton, QAction | None, RibbonItemSpec, QIcon]] = []
        self._ctx_banners: list[tuple[QLabel, str]] = []
        self._groups_by_tab: dict[str, list[RibbonGroupWidget]] = {}

        self._keytip_badges: list[QLabel] = []
        self._keytip_level: str | None = None
        self._keytip_map: dict[str, tuple[str, Any]] = {}
        self._keytip_buf: str = ""
        self._alt_down_alone: bool = False
        self._event_filter_target: QObject | None = None

        self.setObjectName("Paper2016RibbonBar")
        self.setFont(ui_font())

        self._build_ui()
        self._install_shortcuts_and_filters()
        self.refresh_context(force=True)
        if self._current_tab_id:
            self.select_tab(self._current_tab_id)
        if self._collapsed:
            self._panel_wrap.setVisible(False)
        self._update_pin_button()

    @property
    def current_tab_id(self) -> str:
        """Return currently selected tab ID."""
        return self._current_tab_id

    @property
    def is_collapsed(self) -> bool:
        """Return whether the Ribbon command panel is collapsed."""
        return self._collapsed

    @property
    def panel_container(self) -> QWidget:
        """Return the panel container widget hosting the tab stack."""
        return self._panel_wrap

    @property
    def keytip_badges(self) -> list[QLabel]:
        """Return active KeyTip overlay badge widgets."""
        return list(self._keytip_badges)

    def built_tab_ids(self) -> set[str]:
        """Return IDs of tab panels that have already been lazily built."""
        return set(self._tab_panels.keys())

    def active_context_ids(self) -> tuple[str, ...]:
        """Return currently visible contextual set IDs."""
        return self._active_ctx_ids

    def tab_button(self, tab_id: str) -> QToolButton | None:
        """Return the tab strip button for ``tab_id`` if currently present."""
        return self._tab_buttons.get(tab_id)

    def groups_for_tab(self, tab_id: str) -> list[RibbonGroupWidget]:
        """Return group widgets for a built tab."""
        return list(self._groups_by_tab.get(tab_id, ()))

    def resolve_icon(
        self,
        cmd_id: str | None,
        icon_override: str | None = None,
        size: int = 16,
    ) -> QIcon:
        """Resolve icon from override, ActionRegistry action, or ``spec.icons`` catalog."""
        if icon_override and has_office_icon(icon_override):
            return get_office_icon(icon_override, size=size)
        if cmd_id:
            act = self.action_registry.get_action(cmd_id)
            if act is not None and not act.icon().isNull():
                return act.icon()
            icon_name = self.spec.icons.get(cmd_id) or cmd_id
            if has_office_icon(icon_name):
                return get_office_icon(icon_name, size=size)
        return QIcon()

    def _build_ui(self) -> None:
        tok = theme_tokens("paper2016")
        self.setStyleSheet(
            f"""
            QWidget#Paper2016RibbonBar {{
                background: {tok.dock_top};
                border-bottom: 1px solid {tok.tb_border};
            }}
            QWidget#RibbonTopBar {{
                background: {tok.dock_top};
            }}
            QToolButton#RibbonFileButton {{
                background: #008080;
                color: #FFFFFF;
                border: 1px solid #006666;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                padding: 3px 12px;
                font-weight: bold;
            }}
            QToolButton#RibbonFileButton:hover {{
                background: #009494;
            }}
            QToolButton#RibbonTabButton {{
                background: transparent;
                color: #2C2A26;
                border: 1px solid transparent;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                padding: 3px 10px;
            }}
            QToolButton#RibbonTabButton:hover {{
                background: {tok.hot_b};
            }}
            QToolButton#RibbonTabButton:checked {{
                background: #FFFFFF;
                color: #008080;
                border-top: 1px solid {tok.tb_border};
                border-left: 1px solid {tok.tb_border};
                border-right: 1px solid {tok.tb_border};
                border-bottom: 1px solid #FFFFFF;
                font-weight: bold;
            }}
            QWidget#RibbonPanelWrap {{
                background: #FFFFFF;
                border-top: 1px solid {tok.tb_border};
            }}
            QWidget#RibbonPanelWrap QToolButton:hover {{
                background: {tok.menu_hot};
                border: 1px solid #008080;
                border-radius: 2px;
            }}
            QWidget#RibbonPanelWrap QToolButton:checked {{
                background: #D8EEEE;
                border: 1px solid #008080;
                border-radius: 2px;
            }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Top strip: QAT | File | Tabs | Contextual Tabs | Pin
        self._top_bar = QWidget(self)
        self._top_bar.setObjectName("RibbonTopBar")
        self._top_bar.setFixedHeight(30)
        top_layout = QHBoxLayout(self._top_bar)
        top_layout.setContentsMargins(6, 2, 6, 0)
        top_layout.setSpacing(4)

        self._qat_widget = QWidget(self._top_bar)
        self._qat_layout = QHBoxLayout(self._qat_widget)
        self._qat_layout.setContentsMargins(0, 0, 4, 2)
        self._qat_layout.setSpacing(1)
        self._build_qat()
        top_layout.addWidget(self._qat_widget, 0)

        qat_sep = QFrame(self._top_bar)
        qat_sep.setFrameShape(QFrame.Shape.VLine)
        qat_sep.setFixedWidth(1)
        qat_sep.setFixedHeight(16)
        qat_sep.setStyleSheet("background: #B8B0A2; border: none;")
        top_layout.addWidget(qat_sep, 0, Qt.AlignmentFlag.AlignVCenter)

        self._file_btn = QToolButton(self._top_bar)
        self._file_btn.setObjectName("RibbonFileButton")
        self._file_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._file_btn.setText(safe_tr("文件"))
        self._file_btn.setFont(ui_font(9, bold=True))
        self._file_btn.clicked.connect(self._open_file_menu)
        top_layout.addWidget(self._file_btn, 0, Qt.AlignmentFlag.AlignBottom)

        self._tabs_container = QWidget(self._top_bar)
        self._tabs_layout = QHBoxLayout(self._tabs_container)
        self._tabs_layout.setContentsMargins(0, 0, 0, 0)
        self._tabs_layout.setSpacing(2)
        top_layout.addWidget(self._tabs_container, 0, Qt.AlignmentFlag.AlignBottom)

        top_layout.addStretch(1)

        self._pin_btn = QToolButton(self._top_bar)
        self._pin_btn.setObjectName("RibbonPinButton")
        self._pin_btn.setAutoRaise(True)
        self._pin_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._pin_btn.setFixedSize(22, 22)
        self._pin_btn.clicked.connect(lambda _chk=False: self.collapse())
        top_layout.addWidget(self._pin_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        root.addWidget(self._top_bar)

        # 2. Panel area (lazily populated QStackedWidget)
        self._panel_wrap = QWidget(self)
        self._panel_wrap.setObjectName("RibbonPanelWrap")
        self._panel_wrap.setFixedHeight(92)
        wrap_l = QHBoxLayout(self._panel_wrap)
        wrap_l.setContentsMargins(6, 3, 6, 3)
        wrap_l.setSpacing(0)

        self._panel_stack = QStackedWidget(self._panel_wrap)
        wrap_l.addWidget(self._panel_stack, 1)

        root.addWidget(self._panel_wrap)

    def _build_qat(self) -> None:
        for raw in self.spec.qat:
            item = RibbonItemSpec(cmd=raw, size="small") if isinstance(raw, str) else raw
            btn = QToolButton(self._qat_widget)
            btn.setAutoRaise(True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setIconSize(QSize(16, 16))
            btn.setFixedHeight(22)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

            act = self.action_registry.get_action(item.cmd) if item.cmd else None
            fallback = self.resolve_icon(item.cmd, item.icon, 16)
            if act is not None:
                btn.setDefaultAction(act)
                btn.setText("")
                if item.split:
                    btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
                if item.menu_builder is not None:
                    menu = item.menu_builder()
                    if menu is not None:
                        btn.setMenu(menu)
                elif act.menu() is not None:
                    btn.setMenu(act.menu())
                if act.icon().isNull() and not fallback.isNull():
                    btn.setIcon(fallback)
                act.changed.connect(lambda b=btn, a=act, fi=fallback: self._sync_qat_btn(b, a, fi))
            elif not fallback.isNull():
                btn.setIcon(fallback)
            self._qat_layout.addWidget(btn)
            self._qat_buttons.append((btn, act, item, fallback))

    def _sync_qat_btn(self, btn: QToolButton, act: QAction | None, fallback: QIcon) -> None:
        if not is_alive(btn):
            return
        btn.setText("")
        if act is not None:
            btn.setToolTip(_clean_ribbon_label(act.toolTip() or act.text()))
            if act.icon().isNull() and not fallback.isNull():
                btn.setIcon(fallback)

    def _install_shortcuts_and_filters(self) -> None:
        sc = QShortcut(QKeySequence("Ctrl+F1"), self)
        sc.setContext(Qt.ShortcutContext.WindowShortcut)
        sc.activated.connect(self.collapse)
        self._collapse_shortcut = sc

        win = self.window() or self
        win.installEventFilter(self)
        self._event_filter_target = win

    def cleanup(self) -> None:
        """Clear KeyTips and remove event filters before window teardown."""
        self.clear_keytips()
        if self._event_filter_target is not None and is_alive(self._event_filter_target):
            try:
                self._event_filter_target.removeEventFilter(self)
            except Exception:
                pass
        self._event_filter_target = None

    def build_file_menu(self) -> QMenu:
        """Build the File dropdown menu from ``spec.file_actions`` via ActionRegistry."""
        menu = QMenu(self._file_btn)
        last_sep = True
        for aid in self.spec.file_actions:
            if aid == "-":
                if not last_sep:
                    menu.addSeparator()
                    last_sep = True
                continue
            act = self.action_registry.get_action(aid)
            if act is None or not act.isVisible():
                continue
            menu.addAction(act)
            last_sep = False
        return menu

    def _open_file_menu(self) -> None:
        self.clear_keytips()
        menu = self.build_file_menu()
        pos = self._file_btn.mapToGlobal(QPoint(0, self._file_btn.height()))
        menu.exec(pos)

    def _all_tabs(self) -> list[tuple[RibbonTabSpec, RibbonContextSetSpec | None]]:
        out: list[tuple[RibbonTabSpec, RibbonContextSetSpec | None]] = [
            (t, None) for t in self.spec.tabs
        ]
        for ctx in self.spec.contextual:
            for t in ctx.tabs:
                out.append((t, ctx))
        return out

    def _find_tab(self, tab_id: str) -> RibbonTabSpec | None:
        for t, _ctx in self._all_tabs():
            if t.tab_id == tab_id:
                return t
        return None

    def _active_contexts(self) -> list[RibbonContextSetSpec]:
        active: list[RibbonContextSetSpec] = []
        for ctx in self.spec.contextual:
            try:
                if ctx.when():
                    active.append(ctx)
            except Exception:
                logger.debug("Ribbon context predicate %s failed", ctx.set_id, exc_info=True)
        return active

    def _rebuild_tab_strip(self, active_sets: list[RibbonContextSetSpec]) -> None:
        while self._tabs_layout.count():
            item = self._tabs_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._tab_buttons.clear()
        self._ctx_banners.clear()

        for tab in self.spec.tabs:
            btn = self._make_tab_button(tab)
            self._tabs_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignBottom)

        for ctx in active_sets:
            ctx_box = QWidget(self._tabs_container)
            ctx_l = QVBoxLayout(ctx_box)
            ctx_l.setContentsMargins(2, 0, 2, 0)
            ctx_l.setSpacing(0)

            banner = QLabel(safe_tr(ctx.set_label), ctx_box)
            banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            banner.setFont(ui_font(7.5, bold=True))
            banner.setStyleSheet(
                f"background: {ctx.accent}; color: #FFFFFF; padding: 0px 6px; "
                "border-top-left-radius: 2px; border-top-right-radius: 2px;"
            )
            banner.setFixedHeight(12)
            ctx_l.addWidget(banner)
            self._ctx_banners.append((banner, ctx.set_label))

            tabs_row = QWidget(ctx_box)
            row_l = QHBoxLayout(tabs_row)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(1)
            for tab in ctx.tabs:
                btn = self._make_tab_button(tab, ctx_accent=ctx.accent)
                row_l.addWidget(btn)
            ctx_l.addWidget(tabs_row)
            self._tabs_layout.addWidget(ctx_box, 0, Qt.AlignmentFlag.AlignBottom)

        self._sync_tab_checks()

    def _make_tab_button(self, tab: RibbonTabSpec, ctx_accent: str | None = None) -> QToolButton:
        btn = QToolButton(self._tabs_container)
        btn.setObjectName("RibbonTabButton")
        btn.setCheckable(True)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setText(_clean_ribbon_label(safe_tr(tab.label)))
        btn.setFont(ui_font(9))
        if ctx_accent:
            btn.setProperty("ribbonContextAccent", ctx_accent)
        btn.setProperty("ribbonTabId", tab.tab_id)
        btn.clicked.connect(lambda _chk=False, tid=tab.tab_id: self._on_tab_clicked(tid))
        btn.installEventFilter(self)
        self._tab_buttons[tab.tab_id] = btn
        return btn

    def _sync_tab_checks(self) -> None:
        for tid, btn in self._tab_buttons.items():
            if is_alive(btn):
                btn.setChecked(tid == self._current_tab_id)

    def _on_tab_clicked(self, tab_id: str) -> None:
        self.clear_keytips()
        if self._collapsed:
            if self._peeking and self._current_tab_id == tab_id:
                self._end_peek()
                return
            self._peeking = True
            self._panel_wrap.setVisible(True)
        self.select_tab(tab_id)

    def _end_peek(self) -> None:
        if self._peeking:
            self._peeking = False
            if self._collapsed:
                self._panel_wrap.setVisible(False)

    def _ensure_panel(self, tab_id: str) -> QWidget:
        if tab_id in self._tab_panels:
            return self._tab_panels[tab_id]
        tab = self._find_tab(tab_id)
        panel = QWidget(self._panel_stack)
        panel_l = QHBoxLayout(panel)
        panel_l.setContentsMargins(0, 0, 0, 0)
        panel_l.setSpacing(2)

        groups: list[RibbonGroupWidget] = []
        if tab is not None:
            for grp_spec in tab.groups:
                gw = RibbonGroupWidget(
                    grp_spec,
                    self.action_registry,
                    self.resolve_icon,
                    on_command_executed=self._end_peek,
                    parent=panel,
                )
                panel_l.addWidget(gw)
                groups.append(gw)
        panel_l.addStretch(1)

        self._groups_by_tab[tab_id] = groups
        self._tab_panels[tab_id] = panel
        self._panel_stack.addWidget(panel)
        return panel

    def select_tab(self, tab_id: str) -> None:
        """Select and lazily construct the panel for ``tab_id``."""
        if self._find_tab(tab_id) is None and self.spec.tabs:
            tab_id = self.spec.tabs[0].tab_id
        self._current_tab_id = tab_id
        panel = self._ensure_panel(tab_id)
        self._panel_stack.setCurrentWidget(panel)
        self._sync_tab_checks()
        self.fit_groups()

    def collapse(self, on: bool | None = None) -> None:
        """Collapse or expand the Ribbon panel and persist per app."""
        new_state = (not self._collapsed) if on is None else bool(on)
        self._collapsed = new_state
        self._peeking = False
        self._panel_wrap.setVisible(not new_state)
        self._update_pin_button()
        try:
            get_app_settings().set_value(f"ui/ribbon_collapsed_{self.spec.app_id}", new_state)
        except Exception:
            logger.debug("Could not persist ribbon collapse state", exc_info=True)
        self.fit_groups()

    def _update_pin_button(self) -> None:
        if self._collapsed:
            self._pin_btn.setText("▼")
            self._pin_btn.setToolTip(safe_tr("展开功能区 (Ctrl+F1)"))
        else:
            self._pin_btn.setText("▲")
            self._pin_btn.setToolTip(safe_tr("折叠功能区 (Ctrl+F1)"))

    def fit_groups(self) -> None:
        """Fold groups from right to left when viewport narrows below total group width."""
        groups = self._groups_by_tab.get(self._current_tab_id)
        if not groups:
            return
        for g in groups:
            g.set_folded(False)
        avail = self._panel_stack.width() or max(self.width() - 24, 0)
        if avail <= 0:
            return
        for i in range(len(groups) - 1, 0, -1):
            needed = sum(g.sizeHint().width() for g in groups) + max(0, len(groups) - 1) * 2
            if needed <= avail:
                break
            groups[i].set_folded(True)

    def refresh_context(self, force: bool = False) -> None:
        """Re-evaluate contextual tab predicates and update tab strip / active tab."""
        active_sets = self._active_contexts()
        new_sig = tuple(c.set_id for c in active_sets)
        if not force and new_sig == self._active_ctx_ids:
            return
        before = set(self._active_ctx_ids)
        self._active_ctx_ids = new_sig
        self._rebuild_tab_strip(active_sets)

        is_main = any(t.tab_id == self._current_tab_id for t in self.spec.tabs)
        take = next(
            (
                c
                for c in active_sets
                if c.set_id not in before and (c.auto_open or self._current_tab_id == "insert")
            ),
            None,
        )
        if take is not None and take.tabs:
            if is_main:
                self._back_tab_id = self._current_tab_id
            self.select_tab(take.tabs[0].tab_id)
        elif not is_main and not any(
            t.tab_id == self._current_tab_id for c in active_sets for t in c.tabs
        ):
            target = self._back_tab_id or (self.spec.tabs[0].tab_id if self.spec.tabs else "")
            self._back_tab_id = None
            if target:
                self.select_tab(target)
        else:
            self.fit_groups()

    # -- KeyTips ---------------------------------------------------------------

    @staticmethod
    def _assign_keytips(
        items: list[tuple[QWidget, str, str | None, str | None, str | None]],
    ) -> dict[str, tuple[str, Any]]:
        """Assign unambiguous 1- or 2-character KeyTips matching ``ribbon.js``."""
        used: set[str] = set()
        out: dict[str, tuple[str, Any]] = {}
        rest: list[tuple[QWidget, str, str | None, str | None, str | None]] = []

        def shown(lbl: str, en: str | None) -> str:
            if any("A" <= ch.upper() <= "Z" for ch in lbl):
                return lbl
            return en or ""

        def letters(lbl: str, en: str | None) -> list[str]:
            return [ch.upper() for ch in shown(lbl, en) if "A" <= ch.upper() <= "Z"]

        for w, lbl, en, key, tab_id in items:
            if key and key not in used:
                used.add(key)
                out[key] = (tab_id or "", w)
            else:
                rest.append((w, lbl, en, key, tab_id))

        later: list[tuple[QWidget, str, str | None, str | None, str | None]] = []
        rest_initials = [
            letters(lbl, en)[0] if letters(lbl, en) else "" for _, lbl, en, _, _ in rest
        ]
        for idx, (w, lbl, en, key, tab_id) in enumerate(rest):
            ls = letters(lbl, en)
            ch = ls[0] if ls else ""
            if ch and ch not in used and rest_initials.count(ch) == 1:
                used.add(ch)
                out[ch] = (tab_id or "", w)
            else:
                later.append((w, lbl, en, key, tab_id))

        singles = {k for k in used if len(k) == 1}
        abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for w, lbl, en, _key, tab_id in later:
            text = shown(lbl, en).upper()
            ls = [c for c in text if "A" <= c <= "Z"]
            words = [wd for wd in re.split(r"[^A-Z]+", text) if wd]
            firsts = [c for c in (ls + list(abc)) if c not in singles and not c.isdigit()]
            chosen: str | None = None
            seconds = [wd[0] for wd in words[1:]] + ls[1:] + list(abc)
            for a in firsts:
                for b in seconds:
                    cand = a + b
                    if cand not in used:
                        chosen = cand
                        break
                if chosen:
                    break
            if chosen is None:
                chosen = f"Z{len(used)}"
            used.add(chosen)
            out[chosen] = (tab_id or "", w)
        return out

    def show_keytips(self, level: str = "tabs") -> None:
        """Display Alt/F10 KeyTips badges for tabs or current panel commands."""
        self.clear_keytips()
        items: list[tuple[QWidget, str, str | None, str | None, str | None]] = []
        if level == "tabs":
            for i, (btn, act, _it, _fi) in enumerate(self._qat_buttons, start=1):
                if is_alive(btn) and btn.isVisible():
                    txt = act.text() if act else ""
                    items.append((btn, txt, source_to_english(txt), str(i), None))
            file_raw = safe_tr("文件")
            items.append(
                (
                    self._file_btn,
                    _clean_ribbon_label(file_raw),
                    source_to_english("文件") or "File",
                    "F",
                    "file",
                )
            )
            for tab, _ctx in self._all_tabs():
                btn = self._tab_buttons.get(tab.tab_id)
                if btn is not None and is_alive(btn):
                    raw_lbl = safe_tr(tab.label)
                    items.append(
                        (
                            btn,
                            _clean_ribbon_label(raw_lbl),
                            source_to_english(tab.label),
                            _extract_access_key(raw_lbl),
                            tab.tab_id,
                        )
                    )
        else:
            for gw in self._groups_by_tab.get(self._current_tab_id, ()):
                for w, lbl, en in gw.keytip_targets():
                    items.append((w, lbl, en, None, None))

        assigned = self._assign_keytips(items)
        self._keytip_level = level
        self._keytip_map = assigned
        self._keytip_buf = ""

        host = self.window() or self
        for key, (_tab_id, target) in assigned.items():
            if not is_alive(target):
                continue
            badge = QLabel(key, host)
            badge.setObjectName("RibbonKeyTipBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFont(ui_font(7.5, bold=True))
            badge.setStyleSheet(
                "background: #2C2A26; color: #FFFFFF; border: 1px solid #8A8478; "
                "border-radius: 2px; padding: 0px 3px;"
            )
            badge.adjustSize()
            pt = target.mapTo(
                host,
                QPoint(
                    max(0, target.width() // 2 - badge.width() // 2), max(0, target.height() - 8)
                ),
            )
            badge.move(max(0, pt.x()), max(0, pt.y()))
            badge.show()
            badge.raise_()
            self._keytip_badges.append(badge)

    def clear_keytips(self) -> None:
        """Remove all KeyTip overlay badges and exit KeyTips navigation mode."""
        for badge in self._keytip_badges:
            if is_alive(badge):
                badge.hide()
                badge.deleteLater()
        self._keytip_badges.clear()
        self._keytip_level = None
        self._keytip_map.clear()
        self._keytip_buf = ""

    def handle_keytip_char(self, ch: str) -> bool:
        """Process one KeyTip character or Escape; return True if consumed."""
        if self._keytip_level is None:
            return False
        if ch == "Escape":
            if self._keytip_level == "cmds":
                self.show_keytips("tabs")
            else:
                self.clear_keytips()
                self._end_peek()
            return True
        if len(ch) != 1 or not ch.isalnum():
            self.clear_keytips()
            return False

        self._keytip_buf += ch.upper()
        hit = self._keytip_map.get(self._keytip_buf)
        if hit is None:
            if not any(k.startswith(self._keytip_buf) for k in self._keytip_map):
                self._keytip_buf = ""
            return True

        tab_id, target = hit
        level = self._keytip_level
        self.clear_keytips()
        if level == "tabs" and tab_id:
            if tab_id == "file":
                self._open_file_menu()
                return True
            if self._collapsed:
                self._peeking = True
                self._panel_wrap.setVisible(True)
            self.select_tab(tab_id)
            self.show_keytips("cmds")
            return True

        if is_alive(target):
            if isinstance(target, QComboBox):
                target.setFocus()
            elif isinstance(target, QToolButton):
                target.click()
        self._end_peek()
        return True

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        et = event.type()
        if et == QEvent.Type.MouseButtonDblClick and obj in self._tab_buttons.values():
            self.collapse()
            return True
        if obj is self._event_filter_target and isinstance(event, QKeyEvent):
            if et == QEvent.Type.KeyPress:
                key = event.key()
                if key == Qt.Key.Key_F10 and not (
                    event.modifiers()
                    & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
                ):
                    if self._keytip_level is not None:
                        self.clear_keytips()
                    else:
                        self.show_keytips("tabs")
                    return True
                if key == Qt.Key.Key_Alt:
                    self._alt_down_alone = True
                    return False
                self._alt_down_alone = False
                if self._keytip_level is not None:
                    if key == Qt.Key.Key_Escape:
                        return self.handle_keytip_char("Escape")
                    txt = event.text()
                    if txt:
                        return self.handle_keytip_char(txt)
            elif et == QEvent.Type.KeyRelease and event.key() == Qt.Key.Key_Alt:
                if self._alt_down_alone:
                    self._alt_down_alone = False
                    if self._keytip_level is not None:
                        self.clear_keytips()
                    else:
                        self.show_keytips("tabs")
                    return True
                self._alt_down_alone = False
        return super().eventFilter(obj, event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._safe_fit_groups)

    def _safe_fit_groups(self) -> None:
        if is_alive(self):
            self.fit_groups()

    def retranslate_ui(self) -> None:
        """Retranslate File button, tab strip, contextual banners, QAT, and built groups."""
        self._file_btn.setText(safe_tr("文件"))
        self._update_pin_button()

        for tab, _ctx in self._all_tabs():
            btn = self._tab_buttons.get(tab.tab_id)
            if btn is not None and is_alive(btn):
                btn.setText(_clean_ribbon_label(safe_tr(tab.label)))

        for banner, src_label in self._ctx_banners:
            if is_alive(banner):
                banner.setText(safe_tr(src_label))

        for btn, act, _it, fallback in self._qat_buttons:
            self._sync_qat_btn(btn, act, fallback)

        for groups in self._groups_by_tab.values():
            for gw in groups:
                if is_alive(gw):
                    gw.retranslate_ui()
        self.fit_groups()


def find_toolbar_menu(
    window: Any,
    toolbar_name: str,
    cmd_id: str | None = None,
    tooltip_src: str | None = None,
) -> QMenu | None:
    """Locate an existing dropdown/split ``QMenu`` on a classic toolbar without duplicating it."""
    tb = getattr(window, "toolbars", {}).get(toolbar_name)
    if tb is None:
        return None
    if cmd_id:
        reg = getattr(window, "action_registry", None)
        act = reg.get_action(cmd_id) if reg is not None else None
        if act is not None:
            for btn in tb.findChildren(QToolButton):
                if btn.defaultAction() is act and btn.menu() is not None:
                    return btn.menu()
    if tooltip_src:
        translated = safe_tr(tooltip_src)
        for btn in tb.findChildren(QToolButton):
            if btn.menu() is not None and btn.toolTip() in (tooltip_src, translated):
                return btn.menu()
    return None


def toolbar_menu_builder(
    window: Any,
    toolbar_name: str,
    cmd_id: str | None = None,
    tooltip_src: str | None = None,
) -> Callable[[], QMenu]:
    """Return a lazy menu builder reusing an existing toolbar dropdown/split ``QMenu``."""

    def _build() -> QMenu:
        found = find_toolbar_menu(window, toolbar_name, cmd_id=cmd_id, tooltip_src=tooltip_src)
        return found if found is not None else QMenu(window)

    return _build


def make_mirrored_combo(
    source: QComboBox | None,
    on_change: Callable[[str], None],
    width: int,
    tooltip_src: str,
    parent: QWidget,
) -> QComboBox:
    """Create a Ribbon combo box mirrored bidirectionally with a toolbar combo box."""
    combo = QComboBox(parent)
    combo.setFixedWidth(width)
    combo.setFixedHeight(20)
    combo.setFont(ui_font(8.5))
    combo.setToolTip(safe_tr(tooltip_src))
    if source is not None:
        combo.setEditable(source.isEditable())
        items = [source.itemText(i) for i in range(source.count())]
        if items:
            combo.addItems(items)
        combo.setCurrentText(source.currentText())

        def _from_source(txt: str) -> None:
            if is_alive(combo) and combo.currentText() != txt:
                combo.blockSignals(True)
                combo.setCurrentText(txt)
                combo.blockSignals(False)

        source.currentTextChanged.connect(_from_source)
    else:
        combo.setEditable(True)

    combo.currentTextChanged.connect(on_change)
    return combo


def make_ribbon_color_button(
    mode: str,
    default_color: str,
    tooltip_src: str,
    on_applied: Callable[[str], None],
    parent: QWidget,
) -> QWidget:
    """Create a compact ColorPickerButton for Ribbon rows."""
    from atboffice.ui.components.color_picker import ColorPickerButton

    btn = ColorPickerButton(
        mode=mode,
        default_color=default_color,
        tooltip=tooltip_src,
        parent=parent,
    )
    btn.setFixedHeight(20)
    btn.color_applied.connect(on_applied)
    return btn
