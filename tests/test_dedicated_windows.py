"""Unit and integration tests for dedicated office windows: Quire, Ledger, Lectern."""

from pathlib import Path

from PySide6.QtWidgets import QMainWindow

from atboffice.modules.presentation.view import PresentationView
from atboffice.modules.spreadsheet.view import SpreadsheetView
from atboffice.modules.writer.view import WriterView
from atboffice.ui.components.status_bar import StatusBar
from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow


def test_quire_window_init(qtbot) -> None:
    """Test QuireWindow initialization, hierarchy, default title, and document lifecycle."""
    win = QuireWindow()
    qtbot.addWidget(win)

    assert isinstance(win, BaseOfficeWindow)
    assert isinstance(win, QMainWindow)
    assert isinstance(win.centralWidget(), WriterView)
    assert win.writer_view is win.centralWidget()
    assert "Quire" in win.windowTitle()
    assert "未命名文档" in win.windowTitle()
    assert win.is_modified is False

    # Check toolbars
    assert win.toolbar_standard is not None
    assert win.toolbar_formatting is not None


def test_quire_window_with_file_path(tmp_path: Path, qtbot) -> None:
    """Test QuireWindow initialized with a specific file path and do_save."""
    doc_path = tmp_path / "document.docx"
    win = QuireWindow(file_path=doc_path)
    qtbot.addWidget(win)

    assert win.current_file_path == doc_path.resolve()
    assert "document.docx" in win.windowTitle()
    assert "Quire" in win.windowTitle()

    # Test do_save
    assert win.do_save(doc_path) is True
    assert doc_path.exists()


def test_ledger_window_init(qtbot) -> None:
    """Test LedgerWindow initialization, formula bar, status bar, and default title."""
    win = LedgerWindow()
    qtbot.addWidget(win)

    assert isinstance(win, BaseOfficeWindow)
    assert isinstance(win, QMainWindow)
    assert isinstance(win.centralWidget(), SpreadsheetView)
    assert win.spreadsheet_view is win.centralWidget()
    assert "Ledger" in win.windowTitle()
    assert "未命名工作簿" in win.windowTitle()
    assert win.is_modified is False

    # Check status bar
    assert isinstance(win.statusBar(), StatusBar)
    assert win.status_bar is win.statusBar()


def test_ledger_window_with_file_path(tmp_path: Path, qtbot) -> None:
    """Test LedgerWindow initialized with a specific file path and do_save."""
    sheet_path = tmp_path / "budget.xlsx"
    win = LedgerWindow(file_path=sheet_path)
    qtbot.addWidget(win)

    assert win.current_file_path == sheet_path.resolve()
    assert "budget.xlsx" in win.windowTitle()
    assert "Ledger" in win.windowTitle()

    # Test do_save
    assert win.do_save(sheet_path) is True
    assert sheet_path.exists()


def test_lectern_window_init(qtbot) -> None:
    """Test LecternWindow initialization, presentation view, and default title."""
    win = LecternWindow()
    qtbot.addWidget(win)

    assert isinstance(win, BaseOfficeWindow)
    assert isinstance(win, QMainWindow)
    assert isinstance(win.centralWidget(), PresentationView)
    assert win.presentation_view is win.centralWidget()
    assert "Lectern" in win.windowTitle()
    assert "未命名演示文稿" in win.windowTitle()
    assert win.is_modified is False

    # Check presentation toolbar
    assert win.toolbar_standard is not None
    assert win.toolbar_presentation is not None


def test_lectern_window_with_file_path(tmp_path: Path, qtbot) -> None:
    """Test LecternWindow initialized with a specific file path and do_save."""
    deck_path = tmp_path / "slides.pptx"
    win = LecternWindow(file_path=deck_path)
    qtbot.addWidget(win)

    assert win.current_file_path == deck_path.resolve()
    assert "slides.pptx" in win.windowTitle()
    assert "Lectern" in win.windowTitle()

    # Test do_save
    assert win.do_save(deck_path) is True
    assert deck_path.exists()


def test_dedicated_windows_theme_and_retranslate(qtbot) -> None:
    """Test theme switching and dynamic UI retranslation across all dedicated windows."""
    quire = QuireWindow()
    ledger = LedgerWindow()
    lectern = LecternWindow()

    qtbot.addWidget(quire)
    qtbot.addWidget(ledger)
    qtbot.addWidget(lectern)

    # Test theme application
    quire.set_theme("silver")
    assert quire.current_theme == "silver"
    ledger.set_theme("silver")
    assert ledger.current_theme == "silver"
    lectern.set_theme("silver")
    assert lectern.current_theme == "silver"

    quire.set_theme("blue")
    assert quire.current_theme == "blue"

    # Test retranslation
    quire.retranslate_ui()
    ledger.retranslate_ui()
    lectern.retranslate_ui()

    assert "Quire" in quire.windowTitle()
    assert "Ledger" in ledger.windowTitle()
    assert "Lectern" in lectern.windowTitle()


def test_shell_exports() -> None:
    """Verify dedicated window classes are properly re-exported in atboffice.ui.shell."""
    import atboffice.ui.shell as shell

    assert hasattr(shell, "QuireWindow")
    assert hasattr(shell, "LedgerWindow")
    assert hasattr(shell, "LecternWindow")
    assert shell.QuireWindow is QuireWindow
    assert shell.LedgerWindow is LedgerWindow
    assert shell.LecternWindow is LecternWindow
