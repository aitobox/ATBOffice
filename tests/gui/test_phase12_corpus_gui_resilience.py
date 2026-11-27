"""Phase 12 Wave 2 GUI resilience tests across legacy, encrypted, and corrupt corpus files."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QInputDialog, QMessageBox

from atboffice.core.window_manager import WindowManager
from atboffice.modules.writer.models.document import plain_text
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow
from scripts.office_diff.corpus import load_expectations, partition_corpus

DOCS = Path(__file__).resolve().parents[1] / "docs"


@pytest.fixture(autouse=True)
def _reset_wm():
    WindowManager.reset_instance()
    yield
    wm = WindowManager.get_instance()
    wm._is_quitting = True
    for w in list(wm.active_windows):
        w.set_modified(False)
        w.close()
    WindowManager.reset_instance()


def _install_dialog_recorders(monkeypatch) -> list[tuple[str, str, str]]:
    dialogs: list[tuple[str, str, str]] = []
    for level in ("warning", "critical", "information"):
        monkeypatch.setattr(
            QMessageBox,
            level,
            lambda _parent, title, text, *_a, _lvl=level, **_k: (
                dialogs.append((_lvl, str(title), str(text))) or QMessageBox.StandardButton.Ok
            ),
        )
    return dialogs


def test_quire_failed_or_cancelled_abnormal_open_preserves_dirty_document(
    qapp, monkeypatch, tmp_path: Path
) -> None:
    """Unsupported .doc, encrypted cancel/wrong-pw, and corrupt .docx preserve dirty doc."""
    dialogs = _install_dialog_recorders(monkeypatch)
    valid_docx = DOCS / "word/docx/libreoffice__A019_min.docx"
    legacy_doc = DOCS / "word/doc/libreoffice__CVE-2003-0820-1.doc"
    encrypted_docx = DOCS / "word/docx/poi__protected_agile.docx"
    assert valid_docx.exists() and legacy_doc.exists() and encrypted_docx.exists()

    corrupt_docx = tmp_path / "corrupt_probe.docx"
    corrupt_docx.write_bytes(b"NOT_A_DOCX_ARCHIVE")

    win = QuireWindow()
    try:
        win.maybe_save_prompt = lambda: True
        assert win.open_file(valid_docx) is True
        orig_path = win.current_file_path
        win.writer_view.canvas_view.controller.insert_text("UnsavedQuireEdit")
        assert win.is_modified is True

        def _quire_text() -> str:
            return "".join(plain_text(p) for p in win.writer_view.canvas_view.doc.main.paras)

        # 1. Unsupported legacy .doc
        dialogs.clear()
        assert win.open_file(legacy_doc) is False
        assert len(dialogs) >= 1
        assert win.current_file_path == orig_path
        assert win.is_modified is True
        assert "UnsavedQuireEdit" in _quire_text()

        # 2. Encrypted .docx — user cancels password prompt (0 dialogs)
        dialogs.clear()
        monkeypatch.setattr(QInputDialog, "getText", lambda *_a, **_k: ("", False))
        assert win.open_file(encrypted_docx) is False
        assert dialogs == []
        assert win.current_file_path == orig_path
        assert win.is_modified is True
        assert "UnsavedQuireEdit" in _quire_text()

        # 3. Encrypted .docx — wrong password
        dialogs.clear()
        monkeypatch.setattr(QInputDialog, "getText", lambda *_a, **_k: ("wrong-pass", True))
        assert win.open_file(encrypted_docx) is False
        assert len(dialogs) >= 1
        assert win.current_file_path == orig_path
        assert win.is_modified is True
        assert "UnsavedQuireEdit" in _quire_text()

        # 4. Corrupt .docx
        dialogs.clear()
        assert win.open_file(corrupt_docx) is False
        assert len(dialogs) >= 1
        assert win.current_file_path == orig_path
        assert win.is_modified is True
        assert "UnsavedQuireEdit" in _quire_text()
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_ledger_corrupt_open_preserves_dirty_workbook_and_xls_imports_cleanly(
    qapp, monkeypatch
) -> None:
    """Corrupt .xls/.xlsx preserve dirty workbook; valid legacy .xls imports read-only."""
    dialogs = _install_dialog_recorders(monkeypatch)
    valid_xlsx = DOCS / "excel/xlsx/libreoffice__cell-value.xlsx"
    valid_xls = DOCS / "excel/xls/libreoffice__AutoFilter.xls"
    corrupt_samples = [
        DOCS / "excel/xls/libreoffice__CVE-2010-1246-1.xls",
        DOCS / "excel/xls/libreoffice__crash-5.xls",
        DOCS
        / "excel/xlsx/poi__clusterfuzz-testcase-minimized-XLSX2CSVFuzzer-5636439151607808.xlsx",
    ]
    assert valid_xlsx.exists() and valid_xls.exists()
    for sample in corrupt_samples:
        assert sample.exists(), sample

    win = LedgerWindow()
    try:
        win.maybe_save_prompt = lambda: True
        assert win.open_file(valid_xlsx) is True
        orig_path = win.current_file_path
        win.spreadsheet_view.model.set_cell_value(0, 0, "UnsavedLedgerEdit")
        win.set_modified(True)

        for sample in corrupt_samples:
            dialogs.clear()
            assert win.open_file(sample) is False
            assert any(lvl == "critical" for lvl, _t, _m in dialogs)
            assert win.current_file_path == orig_path
            assert win.is_modified is True
            cell = win.spreadsheet_view.model.get_cell(0, 0)
            assert cell is not None and cell.value == "UnsavedLedgerEdit"
    finally:
        win.set_modified(False)
        win.close()

    xls_win = LedgerWindow()
    try:
        xls_win.maybe_save_prompt = lambda: True
        dialogs.clear()
        assert xls_win.open_file(valid_xls) is True
        assert xls_win.is_read_only_import is True
        assert dialogs == []
    finally:
        xls_win.set_modified(False)
        xls_win.close()
        qapp.processEvents()


def test_lectern_unsupported_and_corrupt_open_preserves_dirty_presentation(
    qapp, monkeypatch, tmp_path: Path
) -> None:
    """Unsupported .ppt and corrupt .pptx show warning and preserve dirty presentation."""
    dialogs = _install_dialog_recorders(monkeypatch)
    valid_pptx = DOCS / "powerpoint/pptx/libreoffice__master-slides.pptx"
    legacy_ppt = DOCS / "powerpoint/ppt/libreoffice__CVE-2010-0033-1.ppt"
    assert valid_pptx.exists() and legacy_ppt.exists()

    corrupt_pptx = tmp_path / "corrupt_probe.pptx"
    corrupt_pptx.write_bytes(b"NOT_A_PPTX_ARCHIVE")

    win = LecternWindow()
    try:
        win.maybe_save_prompt = lambda: True
        assert win.open_file(valid_pptx) is True
        orig_path = win.current_file_path
        initial_slides = len(win.presentation.slides)
        win.action_registry.trigger_action("newSlide")
        assert len(win.presentation.slides) == initial_slides + 1
        assert win.is_modified is True

        for sample in (legacy_ppt, corrupt_pptx):
            dialogs.clear()
            assert win.open_file(sample) is False
            assert len(dialogs) >= 1
            assert win.current_file_path == orig_path
            assert win.is_modified is True
            assert len(win.presentation.slides) == initial_slides + 1
    finally:
        win.set_modified(False)
        win.close()
        qapp.processEvents()


def test_all_77_expectations_entries_classified_and_present() -> None:
    """Verify expectations.json cleanly partitions 73 supported and 77 legacy/abnormal files."""
    supported, legacy_or_abnormal = partition_corpus(
        load_expectations(DOCS / "expectations.json"),
        DOCS,
    )
    assert len(supported) == 73
    assert len(legacy_or_abnormal) == 77
    for entry in legacy_or_abnormal:
        assert entry.path.exists(), entry.path
