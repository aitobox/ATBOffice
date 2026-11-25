"""Regression tests for Issue #419: localized corrupt-workbook open error.

The dialog must name the file (not its full path), stay in the active UI
language without appending the raw parser exception, log the diagnostic
exception, and leave the already-open workbook untouched.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from atboffice.core.i18n import get_i18n_manager
from atboffice.core.window_manager import WindowManager
from atboffice.ui.shell.ledger_window import LedgerWindow

CORRUPT_SAMPLE = Path(
    "tests/docs/excel/xlsx/poi__clusterfuzz-testcase-minimized-XLSX2CSVFuzzer-5636439151607808.xlsx"
)


@pytest.fixture(autouse=True)
def _reset_state():
    WindowManager.reset_instance()
    manager = get_i18n_manager()
    previous = manager.current_locale
    yield
    manager.set_locale(previous)
    wm = WindowManager.get_instance()
    for w in list(wm.active_windows):
        w.close()
    WindowManager.reset_instance()


def _capture_dialogs(monkeypatch) -> list[tuple[str, str, str]]:
    dialogs: list[tuple[str, str, str]] = []
    for level in ("critical", "warning"):
        monkeypatch.setattr(
            QMessageBox,
            level,
            lambda parent, title, text, *a, _lvl=level, **kw: dialogs.append((_lvl, title, text)),
        )
    return dialogs


def _open_corrupt(qtbot, monkeypatch, tmp_path: Path, locale: str):
    assert CORRUPT_SAMPLE.exists()
    get_i18n_manager().set_locale(locale)
    sample = tmp_path / CORRUPT_SAMPLE.name
    shutil.copy(CORRUPT_SAMPLE, sample)

    win = LedgerWindow()
    qtbot.addWidget(win)
    win.maybe_save_prompt = lambda: True
    dialogs = _capture_dialogs(monkeypatch)
    assert win.open_file(sample) is False
    assert len(dialogs) == 1
    return win, sample, dialogs[0]


def test_corrupt_workbook_error_is_localized_in_simplified_chinese(
    qtbot, monkeypatch, tmp_path: Path, caplog
):
    with caplog.at_level(logging.ERROR, logger="atboffice.ui.shell.base_window"):
        _win, sample, (level, title, text) = _open_corrupt(qtbot, monkeypatch, tmp_path, "zh-CN")

    assert level == "critical"
    assert title == "打开失败"
    assert text == f"无法打开文件“{sample.name}”：文件已损坏或无法读取。"
    # No full local path and no raw (English) parser exception in the dialog.
    assert str(tmp_path) not in text
    assert "\n" not in text
    assert not any(c.isascii() and c.isalpha() for c in text.replace(sample.name, ""))

    # Diagnostic exception is preserved in the logs instead.
    records = [r for r in caplog.records if r.exc_info is not None]
    assert records, "expected the parser exception to be logged"
    assert sample.name in records[0].getMessage()


def test_corrupt_workbook_error_is_localized_in_english(qtbot, monkeypatch, tmp_path: Path):
    _win, sample, (level, title, text) = _open_corrupt(qtbot, monkeypatch, tmp_path, "en")

    assert level == "critical"
    assert title == "Open Failed"
    assert sample.name in text
    assert str(tmp_path) not in text
    assert "corrupt" in text.lower()
    assert "\n" not in text


def test_rejecting_corrupt_workbook_preserves_open_workbook(qtbot, monkeypatch, tmp_path: Path):
    get_i18n_manager().set_locale("zh-CN")
    good = tmp_path / "good.csv"
    good.write_text("alpha,beta\n1,2\n", encoding="utf-8")
    sample = tmp_path / CORRUPT_SAMPLE.name
    shutil.copy(CORRUPT_SAMPLE, sample)

    win = LedgerWindow()
    qtbot.addWidget(win)
    win.maybe_save_prompt = lambda: True
    dialogs = _capture_dialogs(monkeypatch)

    assert win.open_file(good) is True
    workbook_before = win.spreadsheet_view.workbook
    path_before = win.current_file_path

    assert win.open_file(sample) is False
    assert len(dialogs) == 1
    assert win.spreadsheet_view.workbook is workbook_before
    assert win.current_file_path == path_before
    assert win.is_modified is False


def test_do_open_returning_false_names_file_only(qtbot, monkeypatch, tmp_path: Path):
    get_i18n_manager().set_locale("zh-CN")
    target = tmp_path / "unknown.xlsx"
    target.write_bytes(b"x")

    win = LedgerWindow()
    qtbot.addWidget(win)
    win.maybe_save_prompt = lambda: True
    win.do_open = lambda path: False  # type: ignore[assignment]
    dialogs = _capture_dialogs(monkeypatch)

    assert win.open_file(target) is False
    assert dialogs == [
        ("critical", "打开失败", "无法打开文件“unknown.xlsx”：文件已损坏或无法读取。")
    ]
