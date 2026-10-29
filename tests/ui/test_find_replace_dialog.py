"""Tests for FindReplaceDialog."""

import pytest
from PySide6.QtWidgets import QMessageBox

from atboffice.core.search import (
    SearchController,
    SpreadsheetSearchAdapter,
)
from atboffice.modules.spreadsheet.models.selection_model import SelectionModel
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.ui.dialogs.find_replace_dialog import FindReplaceDialog


@pytest.fixture
def search_setup():
    sheet = SheetDataModel(name="TestSheet")
    sheet.set_cell(0, 0, CellData(value="Project Alpha"))
    sheet.set_cell(1, 0, CellData(value="Project Beta"))
    sheet.set_cell(2, 0, CellData(value="Project Gamma"))
    sel = SelectionModel()
    adapter = SpreadsheetSearchAdapter(model=sheet, selection=sel)
    controller = SearchController()
    controller.set_adapter(adapter)
    return sheet, sel, controller


def test_dialog_creation_and_tabs(qapp, search_setup):
    sheet, sel, controller = search_setup
    dlg = FindReplaceDialog(controller=controller)

    assert dlg.windowTitle() != ""
    assert dlg.tab_widget.count() == 2
    assert dlg.find_edit is not None
    assert dlg.replace_edit is not None

    # Check tab switching
    dlg.show_find()
    assert dlg.tab_widget.currentIndex() == 0

    dlg.show_replace()
    assert dlg.tab_widget.currentIndex() == 1


def test_dialog_find_next_action(qapp, search_setup):
    sheet, sel, controller = search_setup
    dlg = FindReplaceDialog(controller=controller)

    dlg.find_edit.setText("Beta")
    dlg.btn_find_next.click()

    # Selection should now be at (1, 0)
    assert sel.active_cell == (1, 0)


def test_dialog_options_propagation(qapp, search_setup):
    sheet, sel, controller = search_setup
    dlg = FindReplaceDialog(controller=controller)

    dlg.find_edit.setText("alpha")
    dlg.replace_edit.setText("Omega")
    dlg.case_checkbox.setChecked(True)
    dlg.whole_word_checkbox.setChecked(True)
    dlg.radio_up.setChecked(True)

    opts = dlg.get_search_options()
    assert opts.text == "alpha"
    assert opts.replace_text == "Omega"
    assert opts.match_case is True
    assert opts.whole_word is True
    assert opts.direction == "up"


def test_dialog_replace_all(qapp, search_setup, monkeypatch):
    sheet, sel, controller = search_setup
    dlg = FindReplaceDialog(controller=controller)

    # Monkeypatch QMessageBox.information to not block
    info_called = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, text, *args: info_called.append((title, text)),
    )

    dlg.find_edit.setText("Project")
    dlg.replace_edit.setText("Enterprise")
    dlg.btn_replace_all.click()

    assert len(info_called) == 1
    assert "3" in info_called[0][1]
    assert sheet.get_cell_value(0, 0) == "Enterprise Alpha"
    assert sheet.get_cell_value(1, 0) == "Enterprise Beta"
    assert sheet.get_cell_value(2, 0) == "Enterprise Gamma"


def test_dialog_retranslate_ui(qapp, search_setup):
    sheet, sel, controller = search_setup
    dlg = FindReplaceDialog(controller=controller)
    dlg.retranslate_ui()
    assert dlg.btn_find_next.text() != ""
    assert dlg.btn_replace.text() != ""
