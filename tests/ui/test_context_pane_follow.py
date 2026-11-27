"""Tests for Wave 3 Task 1: contextual task pane auto-follow (RB.follow)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from atboffice.core.i18n import load_locale
from atboffice.core.settings import AppSettings
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.spreadsheet.views.object_layer import (
    AnchorType,
    CellAnchorPoint,
    FloatingObject,
)
from atboffice.modules.writer.models.drawing import FloatProperties, PictureItem, ShapeItem
from atboffice.ui.dialogs.options_dialog import OptionsDialog
from atboffice.ui.panes.context_tools_pane import ContextToolsPane
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow


@pytest.fixture(autouse=True)
def _clean_settings_and_locale():
    AppSettings.reset_instance()
    settings = AppSettings.get_instance()
    settings.set_value("view/pane_follows_selection", True)
    yield
    settings.set_value("view/pane_follows_selection", True)
    load_locale("zh-CN")
    AppSettings.reset_instance()


def test_options_dialog_persists_pane_follows_selection(qapp: QApplication) -> None:
    """OptionsDialog View tab exposes and persists ``view/pane_follows_selection``."""
    dlg = OptionsDialog()
    try:
        assert dlg.chk_pane_follows.isChecked() is True
        dlg.chk_pane_follows.setChecked(False)
        dlg.save_to_settings()
        val = AppSettings.get_instance().get_value("view/pane_follows_selection", True)
        assert bool(val) is False

        dlg._on_restore_defaults()
        assert dlg.chk_pane_follows.isChecked() is True
    finally:
        dlg.close()


def test_quire_context_pane_follow_lifecycle(qapp: QApplication) -> None:
    """Quire follows Picture/Shape selection when dock is open and restores prior pane."""
    win = QuireWindow()
    try:
        win.resize(1200, 800)
        win.show()
        qapp.processEvents()

        # 1. Closed dock must never auto-open on object selection.
        assert win.task_pane_dock.isHidden() is True
        shape = ShapeItem(geometry="rect", width=80, height=50, float_pr=FloatProperties())
        win.writer_view.canvas_view.select_float(0, shape)
        assert win.task_pane_dock.isHidden() is True

        # 2. Open dock on "styles", select Shape -> tools-drawing; deselect -> styles.
        win.task_pane_dock.show()
        win.task_pane_dock.show_pane("styles")
        assert win.task_pane_dock.current_pane_id() == "styles"

        win.writer_view.canvas_view.select_float(0, shape)
        assert win.task_pane_dock.current_pane_id() == "tools-drawing"

        # Action state synchronization via QToolButton.setDefaultAction
        draw_pane = win.task_pane_dock.get_pane("tools-drawing")
        assert isinstance(draw_pane, ContextToolsPane)
        rect_act = win.action_registry.get_action("drawRect")
        assert rect_act is not None
        assert any(act is rect_act for _btn, act in draw_pane._buttons)

        # Picture selection -> tools-picture
        pic = PictureItem(width=60, height=40, float_pr=FloatProperties())
        win.writer_view.canvas_view.select_float(0, pic)
        assert win.task_pane_dock.current_pane_id() == "tools-picture"

        # Clear float -> restores "styles"
        win.writer_view.canvas_view.select_float(None, None)
        assert win.task_pane_dock.current_pane_id() == "styles"

        # 3. Narrow window (< 820px) stays put
        win.resize(760, 700)
        qapp.processEvents()
        win.writer_view.canvas_view.select_float(0, shape)
        assert win.task_pane_dock.current_pane_id() == "styles"

        # 4. Option disabled stays put even in wide window
        win.resize(1200, 800)
        qapp.processEvents()
        AppSettings.get_instance().set_value("view/pane_follows_selection", False)
        win.writer_view.canvas_view.select_float(0, shape)
        assert win.task_pane_dock.current_pane_id() == "styles"

        # 5. Locale switch retranslates contextual pane title cleanly
        AppSettings.get_instance().set_value("view/pane_follows_selection", True)
        win.writer_view.canvas_view.select_float(0, shape)
        load_locale("en")
        qapp.processEvents()
        assert win.task_pane_dock._registry["tools-drawing"].title == "Drawing Tools"
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_ledger_context_pane_follow_switches_between_chart_picture_drawing(
    qapp: QApplication,
) -> None:
    """Ledger follows chart, picture, and shape objects and restores prior pane."""
    win = LedgerWindow()
    try:
        win.resize(1200, 800)
        win.show()
        qapp.processEvents()
        win.task_pane_dock.show()
        win.task_pane_dock.show_pane("clipboard")

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
        shape_obj = FloatingObject(
            id=3,
            kind="rect",
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(0, 0),
            to_point=CellAnchorPoint(3, 4),
        )
        for obj in (chart_obj, pic_obj, shape_obj):
            layer.add_object(obj)

        layer.select_object(chart_obj)
        assert win.task_pane_dock.current_pane_id() == "tools-chart"

        layer.select_object(pic_obj)
        assert win.task_pane_dock.current_pane_id() == "tools-picture"

        layer.select_object(shape_obj)
        assert win.task_pane_dock.current_pane_id() == "tools-drawing"

        layer.select_object(None)
        assert win.task_pane_dock.current_pane_id() == "clipboard"
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_lectern_context_pane_follow_covers_table_picture_drawing_and_smartart(
    qapp: QApplication,
) -> None:
    """Lectern follows table, picture, shape, WordArt, and SmartArt selections."""
    win = LecternWindow()
    try:
        win.resize(1200, 800)
        win.show()
        qapp.processEvents()
        win.task_pane_dock.show()
        win.task_pane_dock.show_pane("clipboard")
        assert win.task_pane_dock.current_pane_id() == "clipboard"

        slide = win.presentation.slides[0]
        pic_shape = Shape(id="p1", type="picture", name="Pic 1", x=40, y=40, w=120, h=90)
        rect_shape = Shape(id="r1", type="shape", name="Rect 1", x=180, y=40, w=120, h=90)
        tbl_shape = Shape(
            id="t1",
            type="table",
            name="Table 1",
            x=40,
            y=160,
            w=240,
            h=120,
            tbl={"cols": [{"w": 120}, {"w": 120}], "rows": [{"h": 60, "cells": [{}, {}]}]},
        )
        wa_shape = Shape(id="w1", type="wordart", name="WordArt 1", x=320, y=40, w=140, h=60)
        sa_shape = Shape(
            id="s1",
            type="group",
            name="Diagram 1",
            x=320,
            y=140,
            w=200,
            h=140,
            sa={"layout": "org", "items": [{"text": "Root", "level": 0}]},
        )
        slide.shapes.extend([pic_shape, rect_shape, tbl_shape, wa_shape, sa_shape])
        scene = win.presentation_view.workspace.scene
        scene.load_slide(slide)

        def _select_by_id(sid: str) -> None:
            scene.clearSelection()
            for item in scene.items():
                if getattr(getattr(item, "model", None), "id", None) == sid:
                    item.setSelected(True)
                    break

        _select_by_id("p1")
        assert win.task_pane_dock.current_pane_id() == "tools-picture"

        _select_by_id("t1")
        assert win.task_pane_dock.current_pane_id() == "tools-table"

        _select_by_id("w1")
        assert win.task_pane_dock.current_pane_id() == "tools-wordart"

        _select_by_id("r1")
        assert win.task_pane_dock.current_pane_id() == "tools-drawing"

        _select_by_id("s1")
        assert win.task_pane_dock.current_pane_id() == "smartart_pane"

        scene.clearSelection()
        assert win.task_pane_dock.current_pane_id() == "clipboard"
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()
