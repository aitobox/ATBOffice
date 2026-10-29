"""Tests for shell window Find & Replace integration."""


from atboffice.modules.spreadsheet.models.sheet_model import CellData
from atboffice.modules.writer.models.document import Paragraph, TextItem
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow


def test_quire_window_find_replace_integration(qapp, monkeypatch):
    win = QuireWindow()
    # Add content to writer document
    p1 = Paragraph(id=10, runs=[TextItem("ATBOffice Quire Editor Document.")])
    win.writer_view.canvas_view.doc.main.blocks = [p1]

    # Open Find dialog
    win.open_find_dialog()
    dlg = win._find_replace_dialog
    assert dlg is not None
    assert dlg.isVisible()
    assert dlg.tab_widget.currentIndex() == 0

    # Search for "Editor"
    dlg.find_edit.setText("Editor")
    dlg.btn_find_next.click()

    # CaretController should have selection around "Editor"
    caret = win.writer_view.canvas_view.controller
    assert caret.selection is not None
    assert not caret.selection.is_collapsed
    assert caret.selection.anchor.offset == 16
    assert caret.selection.focus.offset == 22

    # Switch to Replace
    win.open_replace_dialog()
    assert dlg.tab_widget.currentIndex() == 1

    dlg.replace_edit.setText("Processor")
    dlg.btn_replace.click()

    # Verify replacement in document
    p_text = win.writer_view.canvas_view.doc.main.blocks[0].runs[0].text
    assert "ATBOffice Quire Processor Document." in p_text
    win.close()


def test_ledger_window_find_replace_integration(qapp, monkeypatch):
    win = LedgerWindow()
    # Set cells in spreadsheet
    sheet = win.spreadsheet_view.model
    sheet.set_cell(2, 3, CellData(value="TargetCellVal"))

    # Open Find dialog
    win.open_find_dialog()
    dlg = win._find_replace_dialog
    assert dlg is not None
    assert dlg.isVisible()

    dlg.find_edit.setText("TargetCellVal")
    dlg.btn_find_next.click()

    # Selection in SpreadsheetView should be at (2, 3)
    assert win.spreadsheet_view.selection.active_cell == (2, 3)

    # Replace with NewVal
    dlg.replace_edit.setText("UpdatedVal")
    dlg.btn_replace.click()

    assert sheet.get_cell_value(2, 3) == "UpdatedVal"
    win.close()
