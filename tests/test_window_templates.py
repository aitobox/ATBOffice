"""Tests for window template loading and WindowManager template integration."""

from unittest.mock import MagicMock

import pytest

from atboffice.core.templates import TemplateInfo, TemplateRegistry
from atboffice.core.window_manager import WindowManager
from atboffice.ui.shell.base_window import BaseOfficeWindow


@pytest.fixture(autouse=True)
def reset_state():
    """Ensure clean registry and WindowManager singleton state."""
    TemplateRegistry.reset_instance()
    WindowManager.reset_instance()
    yield
    TemplateRegistry.reset_instance()
    WindowManager.reset_instance()


def test_base_window_load_template_success(qtbot):
    """Verify loading a template sets active_template, marks dirty, and updates title."""
    reg = TemplateRegistry.get_instance()
    builder_mock = MagicMock()
    reg.register(
        TemplateInfo(
            id="test_memo",
            name="Test Memo",
            app="generic",
            category="Memos",
            builder=builder_mock,
        )
    )

    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    assert win.active_template is None
    assert not win.is_modified

    success = win.load_template("test_memo")
    assert success is True
    assert win.active_template is not None
    assert win.active_template.id == "test_memo"
    assert win.current_file_path is None
    assert win.is_modified is True
    assert "Test Memo" in win.windowTitle()
    builder_mock.assert_called_once_with(win)


def test_base_window_load_template_not_found(qtbot):
    """Verify loading a non-existent template fails gracefully without crash."""
    win = BaseOfficeWindow()
    qtbot.addWidget(win)

    success = win.load_template("non_existent_id")
    assert success is False
    assert win.active_template is None
    assert win.is_modified is False


def test_base_window_load_template_builder_exception(qtbot):
    """Verify builder exceptions are caught and return False."""
    reg = TemplateRegistry.get_instance()

    def bad_builder(window):
        raise RuntimeError("Builder exploded")

    reg.register(
        TemplateInfo(
            id="bad_tpl",
            name="Bad Template",
            app="generic",
            category="Test",
            builder=bad_builder,
        )
    )

    win = BaseOfficeWindow()
    qtbot.addWidget(win)

    success = win.load_template("bad_tpl")
    assert success is False


def test_window_title_updates_on_save(qtbot, tmp_path):
    """Title shows template name when untitled, and filename once saved."""
    reg = TemplateRegistry.get_instance()
    reg.register(
        TemplateInfo(
            id="report_tpl",
            name="Quarterly Report",
            app="generic",
            category="Reports",
        )
    )

    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    win.load_template("report_tpl")

    assert "Quarterly Report" in win.windowTitle()
    assert "[*]" in win.windowTitle()

    # Once a file path is assigned (e.g. user saved file)
    save_file = tmp_path / "MyReport.docx"
    save_file.write_text("dummy")
    win.current_file_path = save_file
    win.set_modified(False)
    win.update_window_title()

    assert "MyReport.docx" in win.windowTitle()
    assert "Quarterly Report" not in win.windowTitle()


def test_new_file_resets_template(qtbot):
    """Calling new_file() resets active_template back to None."""
    win = BaseOfficeWindow()
    qtbot.addWidget(win)

    win.load_template("letter")
    assert win.active_template is not None

    win.new_file()
    assert win.active_template is None
    assert not win.is_modified


def test_window_manager_open_with_template(qtbot):
    """Verify WindowManager opens Quire, Ledger, and Lectern windows with template_id."""
    wm = WindowManager.get_instance()

    # 1. Quire with template
    win_quire = wm.open_quire(template_id="letter")
    qtbot.addWidget(win_quire)
    assert win_quire in wm.active_windows
    assert win_quire.active_template is not None
    assert win_quire.active_template.id == "letter"
    assert win_quire.current_file_path is None
    assert win_quire.is_modified is True

    # 2. Ledger with template
    win_ledger = wm.open_ledger(template_id="loan")
    qtbot.addWidget(win_ledger)
    assert win_ledger in wm.active_windows
    assert win_ledger.active_template is not None
    assert win_ledger.active_template.id == "loan"
    assert win_ledger.current_file_path is None
    assert win_ledger.is_modified is True

    # 3. Lectern with template
    win_lectern = wm.open_lectern(template_id="status")
    qtbot.addWidget(win_lectern)
    assert win_lectern in wm.active_windows
    assert win_lectern.active_template is not None
    assert win_lectern.active_template.id == "status"
    assert win_lectern.current_file_path is None
    assert win_lectern.is_modified is True

    # 4. open_template convenience helper
    win_tmpl = wm.open_template("memo")
    qtbot.addWidget(win_tmpl)
    assert win_tmpl.active_template is not None
    assert win_tmpl.active_template.id == "memo"
