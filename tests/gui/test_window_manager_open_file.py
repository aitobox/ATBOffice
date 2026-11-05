"""Integration and end-to-end tests for WindowManager and window document open flow."""

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from atboffice.core.window_manager import WindowManager
from atboffice.modules.writer.models.document import all_paragraphs, ptext
from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow


@pytest.fixture(autouse=True)
def clean_window_manager():
    """Reset WindowManager singleton before and after each test."""
    WindowManager.reset_instance()
    yield
    wm = WindowManager.get_instance()
    for win in list(wm.active_windows):
        win.close()
    if wm.start_center is not None:
        wm.start_center.close()
    WindowManager.reset_instance()


def test_window_manager_open_quire_loads_content(qtbot):
    """Test that open_quire with a valid docx parses and binds text into WriterView."""
    docx_path = Path("tests/docs/word/docx/libreoffice__strict.docx").resolve()
    assert docx_path.exists()

    wm = WindowManager.get_instance()
    win = wm.open_quire(docx_path)
    qtbot.addWidget(win)

    assert isinstance(win, QuireWindow)
    assert win.current_file_path == docx_path
    assert docx_path.name in win.windowTitle()

    # Verify central canvas has loaded the document content (not empty/blank)
    doc = win.writer_view.canvas_view.doc
    assert doc is not None
    paras = all_paragraphs(doc, all_stories=True)
    non_empty = [ptext(p).strip() for p in paras if ptext(p).strip()]
    assert len(non_empty) > 0, "Quire document content should be parsed and populated"


def test_window_manager_open_ledger_loads_content(qtbot):
    """Test that open_ledger with a valid xlsx parses and binds workbook into SpreadsheetView."""
    xlsx_path = Path("tests/docs/excel/xlsx/libreoffice__cell-value.xlsx").resolve()
    assert xlsx_path.exists()

    wm = WindowManager.get_instance()
    win = wm.open_ledger(xlsx_path)
    qtbot.addWidget(win)

    assert isinstance(win, LedgerWindow)
    assert win.current_file_path == xlsx_path
    assert xlsx_path.name in win.windowTitle()

    # Verify central spreadsheet view has loaded workbook and sheets
    wb = win.spreadsheet_view.workbook
    assert wb is not None
    assert len(wb.sheets) > 0
    sheet = wb.sheets[0]
    # Check that cells have been populated
    assert len(sheet.cells) > 0, "Ledger spreadsheet cells should be parsed and populated"


def test_window_manager_open_lectern_loads_content(qtbot):
    """Test that open_lectern with valid pptx binds presentation into PresentationView."""
    pptx_path = Path("tests/docs/powerpoint/pptx/poi__56812.pptx").resolve()
    assert pptx_path.exists()

    wm = WindowManager.get_instance()
    win = wm.open_lectern(pptx_path)
    qtbot.addWidget(win)

    assert isinstance(win, LecternWindow)
    assert win.current_file_path == pptx_path
    assert pptx_path.name in win.windowTitle()

    # Verify presentation slides have been loaded
    pres = win.presentation_view.presentation
    assert pres is not None
    assert len(pres.slides) > 0, "Lectern presentation slides should be parsed and populated"


def test_window_manager_open_file_auto(qtbot):
    """Test that open_file_auto dispatches and loads each format correctly."""
    docx_path = Path("tests/docs/word/docx/libreoffice__strict.docx").resolve()
    xlsx_path = Path("tests/docs/excel/xlsx/libreoffice__cell-value.xlsx").resolve()
    pptx_path = Path("tests/docs/powerpoint/pptx/poi__56812.pptx").resolve()

    wm = WindowManager.get_instance()

    w_quire = wm.open_file_auto(docx_path)
    qtbot.addWidget(w_quire)
    assert isinstance(w_quire, QuireWindow)
    assert len(w_quire.writer_view.canvas_view.doc.main.blocks) > 0

    w_ledger = wm.open_file_auto(xlsx_path)
    qtbot.addWidget(w_ledger)
    assert isinstance(w_ledger, LedgerWindow)
    assert len(w_ledger.spreadsheet_view.workbook.sheets) > 0

    w_lectern = wm.open_file_auto(pptx_path)
    qtbot.addWidget(w_lectern)
    assert isinstance(w_lectern, LecternWindow)
    assert len(w_lectern.presentation_view.presentation.slides) > 0


def test_window_direct_init_with_file_path(qtbot):
    """Test that direct construction QuireWindow(file_path=...) loads the document."""
    docx_path = Path("tests/docs/word/docx/libreoffice__strict.docx").resolve()
    win = QuireWindow(file_path=docx_path)
    qtbot.addWidget(win)
    assert win.current_file_path == docx_path
    paras = all_paragraphs(win.writer_view.canvas_view.doc, all_stories=True)
    non_empty = [ptext(p).strip() for p in paras if ptext(p).strip()]
    assert len(non_empty) > 0


def test_open_corpus_broken_symlink_guidance(tmp_path, qtbot, monkeypatch):
    """Test opening a broken symlink targeting atboffice_corpora shows helpful fetch guidance."""
    symlink_path = tmp_path / "broken_corpus_sample.docx"
    os.symlink("../../../.cache/atboffice_corpora/libreoffice/sample.docx", symlink_path)

    assert symlink_path.is_symlink()
    assert not symlink_path.exists()

    captured_warnings = []

    def mock_warning(parent, title, message, *args, **kwargs):
        captured_warnings.append((title, message))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", mock_warning)

    win = BaseOfficeWindow()
    qtbot.addWidget(win)

    opened = win.open_file(symlink_path)
    assert opened is False
    assert len(captured_warnings) == 1
    title, msg = captured_warnings[0]
    assert "fetch_corpora.py" in msg


def test_cli_main_document_loading(qtbot):
    """Test CLI main() with document paths loads content into respective windows."""
    from atboffice.__main__ import main, main_lectern

    docx_path = str(Path("tests/docs/word/docx/libreoffice__strict.docx").resolve())
    xlsx_path = str(Path("tests/docs/excel/xlsx/libreoffice__cell-value.xlsx").resolve())
    pptx_path = str(Path("tests/docs/powerpoint/pptx/poi__56812.pptx").resolve())

    # 1. Direct file via main()
    ret = main(["atboffice", docx_path], exec_app=False)
    assert ret == 0
    wm = WindowManager.get_instance()
    active = list(wm.active_windows)
    assert len(active) == 1
    assert isinstance(active[0], QuireWindow)
    assert len(active[0].writer_view.canvas_view.doc.main.blocks) > 0
    active[0].close()
    wm.reset_instance()

    # 2. Ledger via main()
    ret = main(["atboffice", "ledger", xlsx_path], exec_app=False)
    assert ret == 0
    wm = WindowManager.get_instance()
    active = list(wm.active_windows)
    assert len(active) == 1
    assert isinstance(active[0], LedgerWindow)
    assert len(active[0].spreadsheet_view.workbook.sheets[0].cells) > 0
    active[0].close()
    wm.reset_instance()

    # 3. Lectern via main_lectern()
    ret = main_lectern([pptx_path], exec_app=False)
    assert ret == 0
    wm = WindowManager.get_instance()
    active = list(wm.active_windows)
    assert len(active) == 1
    assert isinstance(active[0], LecternWindow)
    assert len(active[0].presentation_view.presentation.slides) > 0
    active[0].close()
    wm.reset_instance()

