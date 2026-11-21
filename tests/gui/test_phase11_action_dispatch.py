"""Regression tests for issue #437: unified ActionRegistry / MacMenuBar dispatch."""

from __future__ import annotations

from collections import Counter

import pytest
from PySide6.QtWidgets import QMainWindow

from atboffice.core.action_registry import ActionRegistry, ActionSpec
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.mac_menu import MacMenuBar
from atboffice.ui.shell.quire_window import QuireWindow
from atboffice.ui.shell.start_center import StartCenterWindow

FALLBACK_MARKER = "正在联调中"


# ---------------------------------------------------------------------------
# ActionRegistry alias resolution
# ---------------------------------------------------------------------------


def test_alias_set_handler_binds_canonical_spec(qapp) -> None:
    reg = ActionRegistry()
    reg.register_action(ActionSpec(id="print", label="Print"))
    reg.register_alias("file_print", "print")
    calls: list[str] = []

    reg.set_handler("file_print", lambda: calls.append("x"))

    assert reg.get_spec("print").handler is not None
    assert reg.get_spec("file_print") is reg.get_spec("print")
    assert reg.get_action("file_print") is reg.get_action("print")
    reg.get_action("print").trigger()
    assert calls == ["x"]


def test_handler_set_before_alias_registration_is_migrated(qapp) -> None:
    reg = ActionRegistry()
    calls: list[str] = []
    reg.set_handler("edit_undo", lambda: calls.append("undo"))
    reg.register_action(ActionSpec(id="undo", label="Undo"))
    reg.register_alias("edit_undo", "undo")

    assert reg.trigger_action("undo") is True
    assert calls == ["undo"]


def test_reregistering_spec_under_alias_keeps_canonical_handler(qapp) -> None:
    reg = ActionRegistry()
    calls: list[str] = []
    reg.register_action(ActionSpec(id="print", label="Print"))
    reg.register_alias("file_print", "print")
    reg.set_handler("print", lambda: calls.append("p"))

    action = reg.register_action(ActionSpec(id="file_print", label="Print…"))

    assert action is reg.get_action("print")
    action.trigger()
    assert calls == ["p"]


def test_alias_state_updates_reach_shared_action(qapp) -> None:
    reg = ActionRegistry()
    reg.register_action(ActionSpec(id="bullets", label="Bullets", checkable=True))
    reg.register_alias("format_bullets", "bullets")

    reg.set_checked("format_bullets", True)
    reg.set_enabled("format_bullets", False)

    assert reg.is_checked("bullets") is True
    assert reg.is_enabled("bullets") is False
    assert reg.has_action("format_bullets") is True


def test_alias_cannot_shadow_itself(qapp) -> None:
    reg = ActionRegistry()
    reg.register_action(ActionSpec(id="about", label="About"))
    reg.register_alias("about", "about")
    assert reg.resolve_id("about") == "about"


# ---------------------------------------------------------------------------
# MacMenuBar single dispatch with a lightweight window
# ---------------------------------------------------------------------------


class _CountingWindow(QMainWindow):
    """Minimal window exposing every slot name MacMenuBar binds by default."""

    def __init__(self, app_type: str = "quire") -> None:
        self.app_type = app_type
        super().__init__()
        self.calls: Counter[str] = Counter()
        self.action_registry = ActionRegistry(self)

    def _hit(self, name: str) -> None:
        self.calls[name] += 1

    def undo(self) -> None:
        self._hit("undo")

    def paste(self) -> None:
        self._hit("paste")

    def print_document(self) -> None:
        self._hit("print_document")

    def print_workbook(self) -> None:
        self._hit("print_workbook")

    def print_preview(self) -> None:
        self._hit("print_preview")

    def toggle_fullscreen(self) -> None:
        self._hit("fullscreen")

    def show_options_dialog(self) -> None:
        self._hit("options")

    def set_theme(self, theme: str) -> None:
        self._hit(f"theme:{theme}")


@pytest.mark.parametrize(
    ("action_id", "expected"),
    [
        ("undo", "undo"),
        ("edit_undo", "undo"),
        ("paste", "paste"),
        ("file_print_preview", "print_preview"),
        ("view_fullscreen", "fullscreen"),
        ("tools_options", "options"),
        ("theme_luna_silver", "theme:silver"),
    ],
)
def test_menu_action_dispatches_exactly_once(qtbot, action_id: str, expected: str) -> None:
    win = _CountingWindow()
    qtbot.addWidget(win)
    menu = MacMenuBar(win)

    menu.action_map[action_id].trigger()

    assert win.calls[expected] == 1
    assert sum(win.calls.values()) == 1


def test_print_prefers_workbook_printer_and_fires_once(qtbot) -> None:
    win = _CountingWindow(app_type="ledger")
    qtbot.addWidget(win)
    menu = MacMenuBar(win)

    menu.action_map["file_print"].trigger()

    assert win.calls == Counter({"print_workbook": 1})


def test_window_set_handler_replaces_default_binding(qtbot) -> None:
    win = _CountingWindow()
    qtbot.addWidget(win)
    menu = MacMenuBar(win)
    hits: list[str] = []

    win.action_registry.set_handler("edit_undo", lambda: hits.append("custom"))
    menu.action_map["undo"].trigger()

    assert hits == ["custom"]
    assert win.calls["undo"] == 0


def test_bound_action_never_shows_fallback_toast(qtbot) -> None:
    win = _CountingWindow()
    qtbot.addWidget(win)
    menu = MacMenuBar(win)

    for aid in ("undo", "paste", "print", "printPreview", "view_fullscreen", "tools_options"):
        win.statusBar().clearMessage()
        menu.action_map[aid].trigger()
        assert FALLBACK_MARKER not in win.statusBar().currentMessage()


def test_insert_picture_actions_appear_only_once(qtbot) -> None:
    win = _CountingWindow()
    qtbot.addWidget(win)
    menu = MacMenuBar(win)

    insert_actions = menu.menu_map["insert"].actions()
    picture_actions = menu.menu_map["insert_picture_menu"].actions()
    for aid in ("insert_clipart", "insert_picture", "insert_wordart", "insert_shape"):
        act = menu.action_map[aid]
        assert act in picture_actions
        assert act not in insert_actions


@pytest.mark.parametrize(
    ("app_type", "visible", "hidden"),
    [
        ("quire", ["view_web", "view_outline", "wordCount", "stylesPane"],
         ["view_page_break", "insert_function", "background"]),
        ("ledger", ["view_page_break", "insert_function"],
         ["view_web", "view_doc_map", "wordCount", "background"]),
        ("lectern", ["background"],
         ["view_web", "view_page_break", "insert_function", "stylesPane"]),
    ],
)
def test_app_specific_items_gated_by_app_type(
    qtbot, app_type: str, visible: list[str], hidden: list[str]
) -> None:
    win = _CountingWindow(app_type=app_type)
    qtbot.addWidget(win)
    menu = MacMenuBar(win)
    menu.retranslate_ui()

    for aid in visible:
        assert menu.action_map[aid].isVisible(), aid
    for aid in hidden:
        assert not menu.action_map[aid].isVisible(), aid


def test_set_app_type_refreshes_gating(qtbot) -> None:
    win = _CountingWindow(app_type="quire")
    qtbot.addWidget(win)
    menu = MacMenuBar(win)
    assert not menu.action_map["insert_function"].isVisible()

    menu.set_app_type("ledger")

    assert menu.action_map["insert_function"].isVisible()
    assert not menu.action_map["view_web"].isVisible()


# ---------------------------------------------------------------------------
# Real windows
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("window_cls", "method", "action_ids"),
    [
        (QuireWindow, "undo", ["undo", "edit_undo"]),
        (QuireWindow, "paste", ["paste", "edit_paste"]),
        (QuireWindow, "print_document", ["print", "file_print"]),
        (QuireWindow, "print_preview", ["printPreview", "file_print_preview"]),
        (QuireWindow, "toggle_fullscreen", ["view_fullscreen"]),
        (LedgerWindow, "undo", ["undo", "edit_undo"]),
        (LedgerWindow, "print_workbook", ["print", "file_print"]),
        (LedgerWindow, "print_preview", ["printPreview"]),
        (LedgerWindow, "toggle_fullscreen", ["view_fullscreen"]),
        (LecternWindow, "undo", ["undo", "edit_undo"]),
        (LecternWindow, "paste", ["paste"]),
        (LecternWindow, "print_document", ["print", "file_print"]),
        (LecternWindow, "print_preview", ["printPreview"]),
    ],
)
def test_real_window_actions_execute_once(
    qtbot, monkeypatch, window_cls, method: str, action_ids: list[str]
) -> None:
    counter = Counter()
    monkeypatch.setattr(
        window_cls, method, lambda self, *a, **k: counter.update([method]), raising=True
    )
    win = window_cls()
    qtbot.addWidget(win)

    for aid in action_ids:
        counter.clear()
        win.action_registry.get_action(aid).trigger()
        assert counter[method] == 1, (aid, counter)


@pytest.mark.parametrize("window_cls", [QuireWindow, LedgerWindow, LecternWindow])
def test_real_window_options_execute_once(qtbot, monkeypatch, window_cls) -> None:
    counter = Counter()
    for name in ("open_options_dialog", "show_options_dialog"):
        if hasattr(window_cls, name):
            monkeypatch.setattr(
                window_cls, name, lambda self, *a, n=name, **k: counter.update(["options"])
            )
    win = window_cls()
    qtbot.addWidget(win)

    win.action_registry.get_action("tools_options").trigger()

    assert counter["options"] == 1


def test_lectern_alias_handlers_are_not_dropped(qtbot) -> None:
    win = LecternWindow()
    qtbot.addWidget(win)
    reg = win.action_registry

    for alias, canonical in (("file_print", "print"), ("edit_undo", "undo")):
        assert reg.resolve_id(alias) == canonical
        assert reg.get_spec(alias).handler is not None


# ---------------------------------------------------------------------------
# Start Center
# ---------------------------------------------------------------------------


def test_start_center_supported_actions_are_bound(qtbot) -> None:
    win = StartCenterWindow()
    qtbot.addWidget(win)
    reg = win.menu_bar.action_registry

    for aid in ("new", "open", "close", "about", "help", "tools_options",
                "theme_luna_blue", "theme_classic", "theme_selector"):
        spec = reg.get_spec(aid)
        assert spec is not None and spec.handler is not None, aid
        assert reg.is_enabled(aid), aid


def test_start_center_unsupported_editor_actions_disabled(qtbot) -> None:
    win = StartCenterWindow()
    qtbot.addWidget(win)
    reg = win.menu_bar.action_registry

    for aid in ("save", "undo", "paste", "print", "printPreview", "format_font",
                "insert_symbol", "zoom_in", "spelling"):
        assert not reg.is_enabled(aid), aid


def test_start_center_new_opens_template_gallery(qtbot) -> None:
    win = StartCenterWindow()
    qtbot.addWidget(win)

    win.menu_bar.action_map["new"].trigger()

    assert win.stacked_widget.currentWidget() is win.page_templates
