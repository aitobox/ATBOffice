"""Tests for Phase 13C shared SuiteResearchPane and Ledger/Lectern Research & Thesaurus wiring."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolButton

from atboffice.core.i18n import load_locale
from atboffice.modules.common.research_pane import (
    ResearchHostAdapter,
    ResearchSearchHit,
    SuiteResearchPane,
)
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.models.text import TextBody
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.mac_menu import MacMenuBar


def test_suite_research_pane_adapter_callbacks_and_history(qapp: QApplication) -> None:
    """SuiteResearchPane delegates selection/insert/search to adapter, supports history & copy."""
    inserted: list[str] = []
    navigated: list[str] = []
    pane = SuiteResearchPane(
        adapter=ResearchHostAdapter(
            get_selection_text=lambda: "happy",
            insert_text=lambda w: inserted.append(w) or True,
            search_items=lambda q, _lim: [
                ResearchSearchHit(label=f"Hit: {q}", navigate=lambda: navigated.append(q))
            ],
            scope_label="搜索本文档",
            scope_heading="本文档",
            no_matches_label="在此文档中未找到该文字。",
        )
    )
    try:
        pane.open_with_query(service="thesaurus")
        assert pane.query_edit.text() == "happy"

        word_buttons = [
            b
            for b in pane.results_widget.findChildren(QToolButton)
            if isinstance(b.property("_thes_word"), str)
        ]
        assert len(word_buttons) >= 3
        chosen = next(
            b.property("_thes_word")
            for b in word_buttons
            if b.property("_thes_word").lower() != "happy"
        )

        pane.copy_word(chosen)
        assert QGuiApplication.clipboard().text() == chosen

        assert pane.insert_word(chosen) is True
        assert inserted == [chosen]

        # Follow-up lookup enables Back history
        pane.search("traveler")
        assert pane.btn_back.isEnabled() is True
        pane.go_back()
        assert pane.query_edit.text() == "happy"

        # Document search hit invokes navigate callback
        pane.set_service("document")
        pane.search("traveler")
        hits = [
            b for b in pane.results_widget.findChildren(QToolButton) if "Hit: traveler" in b.text()
        ]
        assert len(hits) == 1
        hits[0].click()
        assert navigated == ["traveler"]

        # Retranslation updates labels
        load_locale("en")
        pane.retranslate_ui()
        assert pane.btn_go.text() == "Go"
        assert pane.btn_back.text() == "◄ Back"
    finally:
        load_locale("zh-CN")
        pane.close()
        pane.deleteLater()


def test_ledger_research_pane_thesaurus_undo_and_workbook_search(qapp: QApplication) -> None:
    """Ledger Research/Thesaurus looks up active cell, replaces undoably, and jumps sheets."""
    win = LedgerWindow()
    try:
        win.resize(1200, 800)
        win.show()
        qapp.processEvents()

        wb = win.spreadsheet_view.workbook
        s1 = wb.sheets[0]
        s2 = wb.add_sheet(name="Notes")
        s1.set_cell_value(0, 0, "happy")
        s1.set_cell_value(1, 0, "budget summary")
        s2.set_cell_value(3, 2, "annual budget review")
        win.spreadsheet_view.selection.select_cell(0, 0)

        act_thes = win.action_registry.get_action("thesaurus")
        act_res = win.action_registry.get_action("research")
        assert act_thes is not None and act_thes.isVisible() and act_thes.isEnabled()
        assert act_res is not None and act_res.isVisible() and act_res.isEnabled()
        assert act_thes.shortcut().toString() == "Shift+F7"

        act_thes.trigger()
        qapp.processEvents()

        pane = win.research_pane
        assert win.task_pane_dock.isVisible() is True
        assert win.task_pane_dock.current_pane_id() == "research"
        assert pane.query_edit.text() == "happy"

        word_buttons = [
            b
            for b in pane.results_widget.findChildren(QToolButton)
            if isinstance(b.property("_thes_word"), str)
        ]
        assert len(word_buttons) >= 3
        chosen = next(
            b.property("_thes_word")
            for b in word_buttons
            if b.property("_thes_word").lower() != "happy"
        )

        # Undoable replace of active cell value -> undo restores "happy"
        assert pane.insert_word(chosen) is True
        assert s1.get_cell_value(0, 0) == chosen
        assert win.undo_service().undo() is True
        assert s1.get_cell_value(0, 0) == "happy"

        # History back
        pane.search("budget")
        assert pane.btn_back.isEnabled() is True
        pane.go_back()
        assert pane.query_edit.text() == "happy"

        # Cross-sheet workbook search + click jumps to Sheet2 cell C4 (3, 2)
        pane.set_service("document")
        pane.search("budget")
        hits = [b for b in pane.results_widget.findChildren(QToolButton) if "Notes!C4" in b.text()]
        assert len(hits) == 1
        hits[0].click()
        qapp.processEvents()
        assert wb.active_sheet is s2
        assert win.spreadsheet_view.selection.active_cell == (3, 2)

        # Dynamic i18n retranslation
        load_locale("en")
        qapp.processEvents()
        assert pane.btn_go.text() == "Go"
        assert pane.btn_back.text() == "◄ Back"
        assert win.task_pane_dock._registry["research"].title == "Research"
    finally:
        load_locale("zh-CN")
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_ledger_shift_f7_opens_research(qapp: QApplication) -> None:
    """Pressing Shift+F7 in LedgerWindow opens Research pane with active cell word."""
    win = LedgerWindow()
    try:
        win.resize(1100, 760)
        win.show()
        win.spreadsheet_view.model.set_cell_value(0, 0, "vivid")
        win.spreadsheet_view.selection.select_cell(0, 0)
        win.spreadsheet_view.grid.setFocus()
        qapp.processEvents()

        QTest.keyClick(win, Qt.Key.Key_F7, Qt.KeyboardModifier.ShiftModifier)
        qapp.processEvents()
        assert win.task_pane_dock.isVisible() is True
        assert win.task_pane_dock.current_pane_id() == "research"
        assert win.research_pane.query_edit.text() == "vivid"
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_lectern_research_pane_thesaurus_undo_and_slide_search(qapp: QApplication) -> None:
    """Lectern Research/Thesaurus looks up shape, replaces undoably, searches slides & notes."""
    win = LecternWindow()
    try:
        win.resize(1200, 800)
        win.show()
        qapp.processEvents()

        ws = win.presentation_view.workspace
        pres = win.presentation_view.presentation
        s1 = pres.slides[0]
        s1.shapes.clear()
        s1_shape = Shape(
            id="sh_happy",
            type="shape",
            name="Box 1",
            x=80.0,
            y=80.0,
            w=240.0,
            h=80.0,
            text=TextBody.from_plain_text("happy"),
        )
        s1.shapes.append(s1_shape)

        s2 = Slide(id="sl_2", layout="blank", notes="quarterly milestone notes")
        s2_shape = Shape(
            id="sh_note",
            type="shape",
            name="Box 2",
            x=80.0,
            y=80.0,
            w=240.0,
            h=80.0,
            text=TextBody.from_plain_text("milestone overview"),
        )
        s2.shapes.append(s2_shape)
        pres.slides.append(s2)
        ws._refresh_thumbnails()
        ws.scene.load_slide(s1)
        win.history.reset()

        item = ws.scene.get_shape_item("sh_happy")
        assert item is not None
        item.setSelected(True)
        qapp.processEvents()

        act_thes = win.action_registry.get_action("thesaurus")
        act_res = win.action_registry.get_action("research")
        assert act_thes is not None and act_thes.isVisible() and act_thes.isEnabled()
        assert act_res is not None and act_res.isVisible() and act_res.isEnabled()
        assert act_thes.shortcut().toString() == "Shift+F7"

        act_thes.trigger()
        qapp.processEvents()

        pane = win.research_pane
        assert win.task_pane_dock.isVisible() is True
        assert win.task_pane_dock.current_pane_id() == "research"
        assert pane.query_edit.text() == "happy"

        word_buttons = [
            b
            for b in pane.results_widget.findChildren(QToolButton)
            if isinstance(b.property("_thes_word"), str)
        ]
        assert len(word_buttons) >= 3
        chosen = next(
            b.property("_thes_word")
            for b in word_buttons
            if b.property("_thes_word").lower() != "happy"
        )

        # Undoable replace in selected shape -> undo restores "happy"
        assert pane.insert_word(chosen) is True
        assert win.presentation_view.presentation.slides[0].shapes[0].text.plain_text == chosen
        assert win.undo_service().undo() is True
        assert win.presentation_view.presentation.slides[0].shapes[0].text.plain_text == "happy"

        # History back
        pane.search("milestone")
        assert pane.btn_back.isEnabled() is True
        pane.go_back()
        assert pane.query_edit.text() == "happy"

        # Presentation search finds both shape text and speaker notes on slide 2 and navigates
        pane.set_service("document")
        pane.search("milestone")
        hits = [
            b
            for b in pane.results_widget.findChildren(QToolButton)
            if "[milestone]" in b.text().lower()
        ]
        assert len(hits) == 2
        hits[1].click()
        qapp.processEvents()
        assert ws.current_slide_index == 1

        # Dynamic i18n retranslation
        load_locale("en")
        qapp.processEvents()
        assert pane.btn_go.text() == "Go"
        assert pane.btn_back.text() == "◄ Back"
        assert win.task_pane_dock._registry["research"].title == "Research"
    finally:
        load_locale("zh-CN")
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_lectern_shift_f7_opens_research(qapp: QApplication) -> None:
    """Pressing Shift+F7 in LecternWindow opens Research pane with selected shape word."""
    win = LecternWindow()
    try:
        win.resize(1100, 760)
        win.show()
        ws = win.presentation_view.workspace
        slide = ws.current_slide
        slide.shapes.clear()
        slide.shapes.append(
            Shape(
                id="sh_vivid",
                type="shape",
                name="Vivid Box",
                x=60.0,
                y=60.0,
                w=200.0,
                h=60.0,
                text=TextBody.from_plain_text("vivid clarity"),
            )
        )
        ws.scene.load_slide(slide)
        ws.scene.get_shape_item("sh_vivid").setSelected(True)
        ws.canvas_view.setFocus()
        qapp.processEvents()

        QTest.keyClick(win, Qt.Key.Key_F7, Qt.KeyboardModifier.ShiftModifier)
        qapp.processEvents()
        assert win.task_pane_dock.isVisible() is True
        assert win.task_pane_dock.current_pane_id() == "research"
        assert win.research_pane.query_edit.text() == "vivid"
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_mac_menu_research_and_thesaurus_gating(qapp: QApplication) -> None:
    """MacMenuBar shows research & thesaurus across all three editors and hides them in generic."""
    bar = MacMenuBar(app_type="generic")
    try:
        assert not bar.action_map["research"].isVisible()
        assert not bar.action_map["thesaurus"].isVisible()
        for app_id in ("quire", "ledger", "lectern"):
            bar.set_app_type(app_id)
            assert bar.action_map["research"].isVisible(), app_id
            assert bar.action_map["thesaurus"].isVisible(), app_id
    finally:
        bar.deleteLater()
