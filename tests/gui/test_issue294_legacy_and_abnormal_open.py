"""Regression tests for Issue #294:
- XLS read-only save constraint after import (never overwrite .xls with 0-byte or invalid data)
- Corrupt .xls accurate error dialog (corrupt critical error instead of unsupported warning)
- XML-disguised .xls (e.g. libreoffice__tdf158483.xls) and .doc GUI dispatch via WindowManager
- WindowManager single-invocation on failed open and recent_files protection
- Isolated real-open audit runner across legacy (.doc/.xls/.ppt), encrypted, and corrupt files
- Honest render stage reporting (never mark skipped/unexecuted render as 'ok')
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QMessageBox

from atboffice.core.window_manager import WindowManager
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow


@pytest.fixture(autouse=True)
def _reset_wm():
    WindowManager.reset_instance()
    yield
    wm = WindowManager.get_instance()
    for w in list(wm.active_windows):
        w.close()
    if wm.start_center is not None:
        wm.start_center.close()
    WindowManager.reset_instance()


def test_ledger_imported_xls_enforces_readonly_save_constraint(
    qtbot, monkeypatch, tmp_path: Path
):
    """Imported binary .xls must be read-only for in-place .xls saving, preserving disk bytes."""
    src_xls = Path("tests/docs/excel/xls/libreoffice__AutoFilter.xls")
    assert src_xls.exists()
    xls_copy = tmp_path / "AutoFilter.xls"
    shutil.copy2(src_xls, xls_copy)
    orig_bytes = xls_copy.read_bytes()

    win = LedgerWindow()
    qtbot.addWidget(win)
    win.maybe_save_prompt = lambda: True

    assert win.open_file(xls_copy) is True
    assert win.is_read_only_import is True

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, text, *a, **kw: warnings.append((title, text)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda parent, title, text, *a, **kw: warnings.append((title, text)),
    )

    # Attempt in-place save on imported .xls
    win.spreadsheet_view.model.set_cell_value(0, 0, "ModifiedInMemory")
    win.set_modified(True)
    assert win.save_file() is False
    assert xls_copy.read_bytes() == orig_bytes
    assert len(warnings) >= 1
    assert any(".xlsx" in msg.lower() or "只读" in msg for _, msg in warnings)

    # Attempt explicit save to another .xls path
    warnings.clear()
    other_xls = tmp_path / "other.xls"
    assert win.save_file(other_xls, confirm_overwrite=False) is False
    assert not other_xls.exists()
    assert len(warnings) >= 1

    # Saving as .xlsx succeeds and lifts read-only import state
    xlsx_target = tmp_path / "AutoFilter_converted.xlsx"
    assert win.save_file(xlsx_target, confirm_overwrite=False) is True
    assert xlsx_target.exists() and xlsx_target.stat().st_size > 0
    assert win.current_file_path == xlsx_target.resolve()
    assert win.is_read_only_import is False


def test_corrupt_xls_shows_corrupt_critical_dialog_not_unsupported_format(
    qtbot, monkeypatch
):
    """Corrupt .xls files must trigger a corrupt dialog, not an unsupported format warning."""
    corrupt_samples = [
        Path("tests/docs/excel/xls/libreoffice__CVE-2010-1246-1.xls"),
        Path("tests/docs/excel/xls/libreoffice__crash-5.xls"),
    ]
    for sample in corrupt_samples:
        assert sample.exists()
        win = LedgerWindow()
        qtbot.addWidget(win)
        win.maybe_save_prompt = lambda: True

        dialogs: list[tuple[str, str, str]] = []
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            lambda parent, title, text, *a, **kw: dialogs.append(("warning", title, text)),
        )
        monkeypatch.setattr(
            QMessageBox,
            "critical",
            lambda parent, title, text, *a, **kw: dialogs.append(("critical", title, text)),
        )

        assert win.open_file(sample) is False
        assert len(dialogs) == 1
        level, title, text = dialogs[0]
        assert level == "critical"
        assert "损坏" in text or "无法打开" in text
        assert "暂不支持" not in text


def test_xml_disguised_as_xls_and_doc_dispatched_via_window_manager(
    qtbot, monkeypatch, tmp_path: Path
):
    """XML Spreadsheet named .xls (tdf158483.xls) and HTML named .doc must open cleanly."""
    xml_xls = Path("tests/docs/excel/xls/libreoffice__tdf158483.xls").resolve()
    assert xml_xls.exists()

    wm = WindowManager.get_instance()
    assert wm.detect_app_type(xml_xls) == "ledger"

    win_ledger = wm.open_file_auto(xml_xls)
    qtbot.addWidget(win_ledger)
    assert isinstance(win_ledger, LedgerWindow)
    assert win_ledger.current_file_path == xml_xls
    assert len(win_ledger.spreadsheet_view.workbook.sheets) == 1
    assert len(win_ledger.spreadsheet_view.workbook.sheets[0].cells) > 100

    # HTML disguised with .doc extension
    html_doc = tmp_path / "report_export.doc"
    html_doc.write_text(
        "<html><body><h1>Disguised HTML Doc</h1><p>Paragraph body</p></body></html>",
        encoding="utf-8",
    )
    assert wm.detect_app_type(html_doc) == "quire"
    win_quire = wm.open_file_auto(html_doc)
    qtbot.addWidget(win_quire)
    assert isinstance(win_quire, QuireWindow)
    assert win_quire.current_file_path == html_doc.resolve()

    # Failed open via WindowManager must only prompt once and never pollute recent_files
    wm.recent_files.clear_all()
    dialogs: list[Any] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, text, *a, **kw: dialogs.append((title, text)),
    )
    legacy_doc = Path("tests/docs/word/doc/poi__ThreeColHead.doc").resolve()
    win_failed = wm.open_file_auto(legacy_doc)
    qtbot.addWidget(win_failed)
    assert win_failed.current_file_path is None
    assert len(dialogs) == 1
    assert not any(Path(e.path) == legacy_doc for e in wm.recent_files.get_entries())


def test_real_open_audit_across_all_77_legacy_encrypted_and_corrupt_samples():
    """Verify isolated real GUI open path across all 75 legacy + 1 encrypted + 1 corrupt files."""
    from atboffice.deep.audit.core import (
        CorpusExpectations,
        audit_legacy_and_abnormal_corpus,
        audit_real_open_file,
    )

    manifest = CorpusExpectations("tests/docs/expectations.json")
    report = audit_legacy_and_abnormal_corpus(
        expectations=manifest,
        password_action="cancel",
        execute_render=True,
        timeout=15.0,
    )

    assert report["total"] == 77
    assert report["imported"] == 23
    assert report["rejected"] == 53
    assert report["cancelled"] == 1
    assert report["timeout"] == 0
    assert report["crash"] == 0
    assert report["fail"] == 0
    assert report["unmatched"] == 0
    assert report["rejection_breakdown"] == {"unsupported_format": 50, "corrupt": 3}

    by_file = {r["file"]: r for r in report["results"]}

    # Verify XML-disguised .xls (libreoffice__tdf158483.xls)
    xml_xls_res = by_file["libreoffice__tdf158483.xls"]
    assert xml_xls_res["outcome"] == "imported"
    assert xml_xls_res["dispatched_format"] == "xmlss"
    assert xml_xls_res["read_only"] is False
    assert xml_xls_res["stages"]["render"] == "ok"

    # Verify binary .xls (e.g. poi__51535.xls and libreoffice__AutoFilter.xls)
    for binary_xls_name in ("poi__51535.xls", "libreoffice__AutoFilter.xls"):
        b_res = by_file[binary_xls_name]
        assert b_res["outcome"] == "imported"
        assert b_res["dispatched_format"] == "xls_binary"
        assert b_res["read_only"] is True
        assert b_res["stages"]["render"] == "ok"

    # Verify corrupt .xls and .xlsx are rejected as corrupt with render='skip'
    for corrupt_name in (
        "libreoffice__CVE-2010-1246-1.xls",
        "libreoffice__crash-5.xls",
        "poi__clusterfuzz-testcase-minimized-XLSX2CSVFuzzer-5636439151607808.xlsx",
    ):
        c_res = by_file[corrupt_name]
        assert c_res["outcome"] == "rejected"
        assert c_res["rejection_kind"] == "corrupt"
        assert c_res["stages"]["render"] == "skip"
        assert len(c_res["dialogs"]) >= 1

    # Verify encrypted .docx wrong-password rejection vs cancel
    enc_cancel = by_file["poi__protected_agile.docx"]
    assert enc_cancel["outcome"] == "cancelled"
    assert enc_cancel["stages"]["render"] == "skip"
    assert len(enc_cancel["dialogs"]) == 0

    enc_reject = audit_real_open_file(
        "tests/docs/word/docx/poi__protected_agile.docx",
        password_action="reject",
        execute_render=True,
        expectations=manifest,
        timeout=15.0,
    )
    assert enc_reject["outcome"] == "rejected"
    assert enc_reject["rejection_kind"] == "encrypted"
    assert enc_reject["stages"]["render"] == "skip"
    assert any("密码" in d["message"] for d in enc_reject["dialogs"])


def test_real_open_isolated_timeout_crash_and_unexecuted_render_guard():
    """Verify timeout/crash process isolation and that unexecuted render is never marked 'ok'."""
    from atboffice.deep.audit.core import (
        IsolatedRealOpenRunner,
        audit_corpus_file,
        audit_real_open_file,
    )

    sample_docx = "tests/docs/word/docx/libreoffice__A019_min.docx"
    sample_xls = "tests/docs/excel/xls/libreoffice__AutoFilter.xls"

    # 1. Skipped / unexecuted render must be 'skip', never 'ok'
    res_no_render = audit_corpus_file(sample_docx, execute_render=False, timeout=10.0)
    assert res_no_render["status"] == "ok"
    assert res_no_render["stages"]["render"] == "skip"

    open_no_render = audit_real_open_file(sample_xls, execute_render=False, timeout=10.0)
    assert open_no_render["outcome"] == "imported"
    assert open_no_render["stages"]["render"] == "skip"

    # 2. Isolated timeout termination
    runner = IsolatedRealOpenRunner(timeout=1.0)
    timeout_res = runner.run(sample_xls, fault="hang")
    assert timeout_res["outcome"] == "timeout"
    assert timeout_res.get("terminated") is True
    assert timeout_res["stages"]["render"] == "skip"

    # 3. Isolated crash capture
    crash_res = runner.run(sample_xls, fault="crash")
    assert crash_res["outcome"] == "crash"
    assert crash_res.get("exitcode") != 0
    assert crash_res["stages"]["render"] == "skip"

