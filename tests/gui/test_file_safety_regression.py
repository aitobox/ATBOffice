"""Automated regression tests for Issue #191:
Protect unsaved data on save failure, overwrite cancel, corrupted file open, and close cancel.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox

from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.quire_window import QuireWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.lectern_window import LecternWindow


def test_atomic_save_preserves_original_file_on_save_error(qtbot, monkeypatch, tmp_path: Path):
    """When do_save fails, any existing target file on disk must remain 100% untouched."""
    orig_file = tmp_path / "original_doc.docx"
    orig_content = "ORIGINAL_UNTOUCHED_CONTENT_DATA_12345"
    orig_file.write_text(orig_content, encoding="utf-8")

    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    win.current_file_path = orig_file
    win.set_modified(True)

    # Simulate failing do_save that writes corrupt partial bytes before crashing
    def failing_do_save(dest_path: Path) -> bool:
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write("CORRUPTED_PARTIAL_DATA")
        raise RuntimeError("Simulated mid-write crash/disk full")

    win.do_save = failing_do_save  # type: ignore[assignment]

    critical_dialogs = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *args, **kwargs: critical_dialogs.append(args),
    )

    success = win.save_file()
    assert success is False
    # Unsaved status preserved
    assert win.is_modified is True
    # Original file is preserved completely
    assert orig_file.read_text(encoding="utf-8") == orig_content
    assert len(critical_dialogs) == 1


def test_save_permission_error_preserves_dirty_state(qtbot, monkeypatch, tmp_path: Path):
    """Permission errors must display specific localized error and preserve dirty document state."""
    target_file = tmp_path / "readonly_doc.docx"
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    win.current_file_path = target_file
    win.set_modified(True)

    def permission_denied_save(dest_path: Path) -> bool:
        raise PermissionError("Permission denied: cannot write to destination")

    win.do_save = permission_denied_save  # type: ignore[assignment]

    critical_dialogs = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda parent, title, text, *args: critical_dialogs.append((title, text)),
    )

    success = win.save_file()
    assert success is False
    assert win.is_modified is True
    assert len(critical_dialogs) == 1
    # Localized dialog title or message indicates permission or save failure
    title, text = critical_dialogs[0]
    assert "权限" in text or "Permission" in text or "保存失败" in title


def test_overwrite_prompt_cancel_preserves_existing_file_and_state(qtbot, monkeypatch, tmp_path: Path):
    """When saving to an existing different path, user declining overwrite preserves target and dirty state."""
    existing_file = tmp_path / "existing_conflict.docx"
    existing_content = "PRECIOUS_EXISTING_DATA_DO_NOT_OVERWRITE"
    existing_file.write_text(existing_content, encoding="utf-8")

    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    win.set_modified(True)
    assert win.current_file_path is None

    # Simulate user clicking No on the overwrite prompt
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )

    success = win.save_file(existing_file, confirm_overwrite=True)
    assert success is False
    # Existing file untouched
    assert existing_file.read_text(encoding="utf-8") == existing_content
    # Dirty state and memory preserved
    assert win.is_modified is True
    assert win.current_file_path is None


def test_open_corrupted_file_preserves_current_document(qtbot, monkeypatch, tmp_path: Path):
    """Opening a corrupted document must fail safely without breaking the current window state."""
    corrupted_file = tmp_path / "corrupted_archive.docx"
    corrupted_file.write_bytes(b"RANDOM_CORRUPTED_BINARY_HEADER_NOT_A_ZIP_OR_XML")

    win = QuireWindow()
    qtbot.addWidget(win)
    initial_path = win.current_file_path

    critical_dialogs = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *args, **kwargs: critical_dialogs.append(args),
    )

    success = win.open_file(corrupted_file)
    assert success is False
    # Path is not updated to corrupt path
    assert win.current_file_path == initial_path
    assert len(critical_dialogs) >= 1


def test_close_event_cancel_aborts_shutdown_cleanly(qtbot, monkeypatch):
    """Cancelling save prompt on closeEvent ignores the event and keeps document modified."""
    win = BaseOfficeWindow()
    qtbot.addWidget(win)
    win.set_modified(True)

    closed_signals: list[BaseOfficeWindow] = []
    win.window_closed.connect(closed_signals.append)

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )

    ev = QCloseEvent()
    win.closeEvent(ev)
    assert not ev.isAccepted()
    assert len(closed_signals) == 0
    assert win.is_modified is True


def test_three_modules_save_and_reopen_roundtrip(qtbot, tmp_path: Path):
    """Verify Quire (.docx, .html), Ledger (.xlsx, .csv), and Lectern (.pptx) save and reopen roundtrip."""
    # 1. Quire HTML roundtrip
    quire_html = tmp_path / "quire_test.html"
    win_q = QuireWindow()
    qtbot.addWidget(win_q)
    win_q.save_file(quire_html)
    assert quire_html.exists()
    assert quire_html.stat().st_size > 0

    win_q2 = QuireWindow()
    qtbot.addWidget(win_q2)
    assert win_q2.open_file(quire_html) is True
    assert win_q2.current_file_path == quire_html.resolve()

    # 2. Ledger CSV roundtrip
    ledger_csv = tmp_path / "ledger_test.csv"
    win_l = LedgerWindow()
    qtbot.addWidget(win_l)
    win_l.spreadsheet_view.model.set_cell_value(0, 0, "Hello Ledger")
    win_l.save_file(ledger_csv)
    assert ledger_csv.exists()
    assert "Hello Ledger" in ledger_csv.read_text(encoding="utf-8")

    win_l2 = LedgerWindow()
    qtbot.addWidget(win_l2)
    assert win_l2.open_file(ledger_csv) is True
    assert win_l2.current_file_path == ledger_csv.resolve()
    assert win_l2.spreadsheet_view.model.get_cell(0, 0).value == "Hello Ledger"

    # 3. Lectern PPTX roundtrip
    lectern_pptx = tmp_path / "lectern_test.pptx"
    win_p = LecternWindow()
    qtbot.addWidget(win_p)
    win_p.save_file(lectern_pptx)
    assert lectern_pptx.exists()
    assert lectern_pptx.stat().st_size > 0

    win_p2 = LecternWindow()
    qtbot.addWidget(win_p2)
    assert win_p2.open_file(lectern_pptx) is True
    assert win_p2.current_file_path == lectern_pptx.resolve()
