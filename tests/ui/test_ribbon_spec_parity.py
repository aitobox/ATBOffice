"""Tests for Phase 12 Wave 3 Task 2: Lazy Paper 2016 Ribbon Mode & Spec Parity."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QToolButton

from atboffice.core.i18n import load_locale
from atboffice.core.settings import AppSettings
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.spreadsheet.views.object_layer import (
    AnchorType,
    CellAnchorPoint,
    FloatingObject,
)
from atboffice.modules.writer.models.drawing import FloatProperties, PictureItem, ShapeItem
from atboffice.ui.components.ribbon_bar import RibbonBar, RibbonItemSpec, RibbonSpec
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow


@pytest.fixture(autouse=True)
def _clean_ribbon_settings_and_locale():
    AppSettings.reset_instance()
    settings = AppSettings.get_instance()
    for app_id in ("quire", "ledger", "lectern"):
        settings.set_value(f"ui/ribbon_collapsed_{app_id}", False)
    load_locale("zh-CN")
    yield
    for app_id in ("quire", "ledger", "lectern"):
        settings.set_value(f"ui/ribbon_collapsed_{app_id}", False)
    load_locale("zh-CN")
    AppSettings.reset_instance()


def _iter_spec_commands(spec: RibbonSpec) -> list[str]:
    """Collect every non-separator command ID and launcher referenced by ``spec``."""
    cmds: list[str] = []

    def _walk_item(it: RibbonItemSpec | str) -> None:
        if isinstance(it, str):
            if it != "|":
                cmds.append(it)
            return
        if it.cmd:
            cmds.append(it.cmd)
        if it.row:
            for sub in it.row:
                _walk_item(sub)

    for q in spec.qat:
        _walk_item(q)
    for fa in spec.file_actions:
        if fa != "-":
            cmds.append(fa)
    for tab in spec.tabs:
        for grp in tab.groups:
            if grp.launcher:
                cmds.append(grp.launcher)
            for item in grp.items:
                _walk_item(item)
    for ctx in spec.contextual:
        for tab in ctx.tabs:
            for grp in tab.groups:
                if grp.launcher:
                    cmds.append(grp.launcher)
                for item in grp.items:
                    _walk_item(item)
    return cmds


@pytest.mark.parametrize("win_cls", [QuireWindow, LedgerWindow, LecternWindow])
def test_default_blue_keeps_ribbon_unbuilt_and_paper2016_lazily_mounts(
    qapp: QApplication, win_cls
) -> None:
    """Default 'blue' never instantiates RibbonBar; switching to 'paper2016' builds it lazily."""
    win = win_cls()
    try:
        win.resize(1280, 820)
        win.show()
        qapp.processEvents()

        # 1. Default blue keeps ribbon_bar unbuilt and classic toolbars visible
        assert win.ribbon_bar is None
        assert getattr(win, "_ribbon_toolbar_host", None) is None
        assert win.toolbars["standard"].isVisible() is True
        assert win.toolbars["formatting"].isVisible() is True

        # 2. Switch to paper2016 -> builds RibbonBar, hides classic toolbars
        win.set_theme("paper2016")
        qapp.processEvents()

        assert isinstance(win.ribbon_bar, RibbonBar)
        assert win._ribbon_toolbar_host is not None
        assert win._ribbon_toolbar_host.isVisible() is True
        assert all(not tb.isVisible() for tb in win.toolbars.values())

        # 3. Lazy tab panel construction: only initial tab is built at first
        built_initial = win.ribbon_bar.built_tab_ids()
        assert built_initial == {win.ribbon_bar.spec.tabs[0].tab_id}
        second_tab = win.ribbon_bar.spec.tabs[1].tab_id
        win.ribbon_bar.select_tab(second_tab)
        assert second_tab in win.ribbon_bar.built_tab_ids()

        # 4. Walk every cmd and launcher in spec: must exist, be handled+visible, and have icon
        all_cmds = _iter_spec_commands(win.ribbon_bar.spec)
        assert len(all_cmds) > 20
        for cmd in all_cmds:
            act = win.action_registry.get_action(cmd)
            assert act is not None, f"{win_cls.__name__}: missing action {cmd!r}"
            assert act.isVisible() is True, f"{win_cls.__name__}: hidden action {cmd!r}"
            assert win.action_registry.has_command(cmd) is True, (
                f"{win_cls.__name__}: unhandled action {cmd!r}"
            )
            icon = win.ribbon_bar.resolve_icon(cmd)
            assert not icon.isNull(), f"{win_cls.__name__}: null icon for {cmd!r}"

        # 5. Switch back to blue -> restores classic toolbars and hides ribbon host
        win.set_theme("blue")
        qapp.processEvents()
        assert win._ribbon_toolbar_host.isVisible() is False
        assert win.toolbars["standard"].isVisible() is True
        assert win.toolbars["formatting"].isVisible() is True
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_quire_ribbon_contextual_tabs_and_auto_open(qapp: QApplication) -> None:
    """Quire Ribbon shows contextual tabs on selection, auto-opens from Insert, and restores."""
    win = QuireWindow()
    try:
        win.resize(1280, 820)
        win.show()
        win.set_theme("paper2016")
        qapp.processEvents()

        rb = win.ribbon_bar
        assert rb is not None
        assert rb.active_context_ids() == ()

        # Select Picture while on Home -> contextual set appears, stays on Home
        pic = PictureItem(width=60, height=40, float_pr=FloatProperties())
        win.writer_view.canvas_view.select_float(0, pic)
        assert "picture" in rb.active_context_ids()
        assert rb.current_tab_id == "home"

        # Clear, switch to Insert, select Shape -> auto-opens drawingFormat, clear restores Insert
        win.writer_view.canvas_view.select_float(None, None)
        assert rb.active_context_ids() == ()
        rb.select_tab("insert")
        shape = ShapeItem(geometry="rect", width=80, height=50, float_pr=FloatProperties())
        win.writer_view.canvas_view.select_float(0, shape)
        assert "drawing" in rb.active_context_ids()
        assert rb.current_tab_id == "drawingFormat"

        win.writer_view.canvas_view.select_float(None, None)
        assert "drawing" not in rb.active_context_ids()
        assert rb.current_tab_id == "insert"

        # Classic toolbars must remain hidden while in paper2016
        assert all(not tb.isVisible() for tb in win.toolbars.values())
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_ledger_ribbon_contextual_tabs(qapp: QApplication) -> None:
    """Ledger Ribbon updates contextual tabs for chart, picture, and drawing objects."""
    win = LedgerWindow()
    try:
        win.resize(1280, 820)
        win.show()
        win.set_theme("paper2016")
        qapp.processEvents()

        rb = win.ribbon_bar
        assert rb is not None
        layer = win.spreadsheet_view.object_layer
        chart_obj = FloatingObject(
            id=1,
            kind="chart",
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(0, 0),
            to_point=CellAnchorPoint(3, 4),
        )
        pic_obj = FloatingObject(
            id=2,
            kind="image",
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(0, 0),
            to_point=CellAnchorPoint(3, 4),
        )
        layer.add_object(chart_obj)
        layer.add_object(pic_obj)

        layer.select_object(chart_obj)
        assert "chart" in rb.active_context_ids()

        layer.select_object(pic_obj)
        assert "picture" in rb.active_context_ids()
        assert "chart" not in rb.active_context_ids()

        layer.select_object(None)
        assert rb.active_context_ids() == ()
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_lectern_ribbon_contextual_tabs_and_master(qapp: QApplication) -> None:
    """Lectern Ribbon shows contextual tabs for picture/shape/table/wordart/smartart/master."""
    win = LecternWindow()
    try:
        win.resize(1280, 820)
        win.show()
        win.set_theme("paper2016")
        qapp.processEvents()

        rb = win.ribbon_bar
        assert rb is not None

        slide = win.presentation.slides[0]
        pic = Shape(id="p1", type="picture", name="Pic 1", x=40, y=40, w=120, h=90)
        tbl = Shape(
            id="t1",
            type="table",
            name="Table 1",
            x=40,
            y=160,
            w=240,
            h=120,
            tbl={"cols": [120, 120], "rows": [{"h": 60, "cells": [{}, {}]}]},
        )
        slide.shapes.extend([pic, tbl])
        scene = win.presentation_view.workspace.scene
        scene.load_slide(slide)

        for item in scene.items():
            if getattr(getattr(item, "model", None), "id", None) == "p1":
                item.setSelected(True)
                break
        assert "picture" in rb.active_context_ids()

        scene.clearSelection()
        for item in scene.items():
            if getattr(getattr(item, "model", None), "id", None) == "t1":
                item.setSelected(True)
                break
        assert "table" in rb.active_context_ids()

        scene.clearSelection()
        assert rb.active_context_ids() == ()

        # Slide Master view auto-opens master contextual tab and closes back to prior tab
        win.set_view_mode("master")
        assert "master" in rb.active_context_ids()
        assert rb.current_tab_id == "masterTab"

        win.set_view_mode("normal")
        assert "master" not in rb.active_context_ids()
        assert rb.current_tab_id == "home"
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_ribbon_collapse_keytips_folding_and_i18n(qapp: QApplication) -> None:
    """Collapse persistence, narrow folding, KeyTips overlay, File menu, and i18n retranslate."""
    win = QuireWindow()
    try:
        win.resize(1280, 820)
        win.show()
        win.set_theme("paper2016")
        qapp.processEvents()

        rb = win.ribbon_bar
        assert rb is not None
        assert rb.is_collapsed is False
        assert rb.panel_container.isVisible() is True

        # Collapse & persist
        rb.collapse(True)
        assert rb.is_collapsed is True
        assert rb.panel_container.isVisible() is False
        assert (
            bool(AppSettings.get_instance().get_value("ui/ribbon_collapsed_quire", False)) is True
        )

        rb.collapse(False)
        assert rb.is_collapsed is False
        assert rb.panel_container.isVisible() is True
        assert (
            bool(AppSettings.get_instance().get_value("ui/ribbon_collapsed_quire", True)) is False
        )

        # Narrow-window group folding
        win.resize(480, 700)
        qapp.processEvents()
        rb.fit_groups()
        groups = rb.groups_for_tab("home")
        assert any(g.is_folded for g in groups[1:])

        win.resize(1280, 820)
        qapp.processEvents()
        rb.fit_groups()
        assert all(not g.is_folded for g in groups)

        # KeyTips overlay & keyboard navigation
        rb.show_keytips("tabs")
        assert len(rb.keytip_badges) > 0
        # Navigate into a tab's command KeyTips using a tab's assigned key, then Esc back & close
        tab_key = next(k for k, (tid, _w) in rb._keytip_map.items() if tid and tid != "file")
        assert rb.handle_keytip_char(tab_key) is True
        assert rb._keytip_level == "cmds"
        assert rb.handle_keytip_char("Escape") is True
        assert rb._keytip_level == "tabs"
        assert rb.handle_keytip_char("Escape") is True
        assert len(rb.keytip_badges) == 0

        # File menu builds from file_actions
        file_menu = rb.build_file_menu()
        assert len(file_menu.actions()) >= len([a for a in rb.spec.file_actions if a != "-"])

        # Dynamic i18n retranslation
        home_btn = rb.tab_button("home")
        assert isinstance(home_btn, QToolButton)
        assert home_btn.text() == "开始"
        load_locale("en")
        qapp.processEvents()
        assert home_btn.text() == "Home"
        load_locale("zh-CN")
        qapp.processEvents()
        assert home_btn.text() == "开始"
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


@pytest.mark.parametrize(
    ("win_cls", "toolbar_name"),
    [
        (LedgerWindow, "chart"),
        (QuireWindow, "tables"),
        (LecternWindow, "tables"),
    ],
)
def test_set_toolbar_mode_does_not_leak_classic_toolbar_in_ribbon_mode(
    qapp: QApplication, win_cls, toolbar_name: str
) -> None:
    """Defer toolbar visibility in paper2016 instead of showing classic QToolBar."""
    win = win_cls()
    try:
        win.resize(1280, 820)
        win.show()
        win.set_theme("paper2016")
        qapp.processEvents()

        win.set_toolbar_mode(toolbar_name, True)
        qapp.processEvents()

        assert win.toolbars[toolbar_name].isHidden() is True
        assert win._classic_toolbar_visibility[toolbar_name] is True

        win.set_theme("classic")
        qapp.processEvents()

        assert win.toolbars[toolbar_name].isHidden() is False
    finally:
        win.set_theme("blue")
        win.set_modified(False)
        win.close()
        qapp.processEvents()
