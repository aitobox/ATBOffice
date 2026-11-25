"""Regression tests for Issue #418: XLS corpus expectations reflect real import results.

23 of the 25 checked-in .xls fixtures import (22 BIFF8 read-only, 1 SpreadsheetML XML
disguised as .xls); two malformed files are rejected with a corrupt error. The manifest
classification and the stage audit must agree with that observed behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from atboffice.deep.audit.core import AuditSession, CorpusExpectations, audit_corpus_file
from atboffice.ui.shell.ledger_window import LedgerWindow

MANIFEST = Path("tests/docs/expectations.json")
CORRUPT_XLS = {"libreoffice__CVE-2010-1246-1.xls", "libreoffice__crash-5.xls"}
XML_DISGUISED_XLS = "libreoffice__tdf158483.xls"


@pytest.fixture(scope="module")
def manifest() -> CorpusExpectations:
    return CorpusExpectations(MANIFEST)


def _xls_items(manifest: CorpusExpectations) -> list[dict]:
    return [it for it in manifest.items if it["format"] == "xls"]


def test_xls_manifest_records_23_imports_and_2_corrupt(manifest: CorpusExpectations) -> None:
    items = _xls_items(manifest)
    assert len(items) == 25
    by_cat: dict[str, set[str]] = {}
    for it in items:
        by_cat.setdefault(it["category"], set()).add(it["file"])
    assert by_cat.get("corrupt") == CORRUPT_XLS
    assert len(by_cat.get("legacy_imported", set())) == 23
    assert "unsupported_format" not in by_cat


def test_xls_manifest_entries_are_internally_consistent(manifest: CorpusExpectations) -> None:
    for it in _xls_items(manifest):
        exp = it["expectations"]
        real_open = it["real_open"]
        notes = it["notes"].lower()
        assert "out of scope" not in notes, it["file"]
        if it["category"] == "legacy_imported":
            assert exp == {
                "parse": "ok",
                "model": "ok",
                "render": "ok",
                "roundtrip": "skip",
                "expected_status": "imported",
            }, it["file"]
            assert real_open["expected_outcome"] == "imported", it["file"]
            if it["file"] == XML_DISGUISED_XLS:
                assert real_open["dispatched_format"] == "xmlss"
                assert "xml" in notes
            else:
                assert real_open["dispatched_format"] == "xls_binary"
                assert real_open["read_only"] is True
                assert "read-only" in notes
        else:
            assert it["category"] == "corrupt"
            assert exp["parse"] == "rejected_corrupt"
            assert exp["expected_status"] == "corrupt"
            assert real_open["expected_outcome"] == "rejected"
            assert real_open["rejection_kind"] == "corrupt"


def test_successful_xls_stage_audit_reports_imported(manifest: CorpusExpectations) -> None:
    for sample in (
        "tests/docs/excel/xls/libreoffice__AutoFilter.xls",
        f"tests/docs/excel/xls/{XML_DISGUISED_XLS}",
    ):
        res = audit_corpus_file(sample, expectations=manifest, timeout=20.0)
        assert res["status"] == "imported", res
        assert res["stages"] == {
            "parse": "ok",
            "model": "ok",
            "render": "ok",
            "roundtrip": "skip",
        }
        assert res["expected_match"] is True


def test_corrupt_xls_stage_audit_reports_corrupt(manifest: CorpusExpectations) -> None:
    for name in sorted(CORRUPT_XLS):
        res = audit_corpus_file(f"tests/docs/excel/xls/{name}", expectations=manifest, timeout=20.0)
        assert res["status"] == "corrupt", res
        assert res["stages"]["parse"] == "rejected_corrupt"
        assert res["stages"]["render"] == "skip"
        assert res["expected_match"] is True


def test_audit_session_counts_imported_results() -> None:
    session = AuditSession()
    session.record_result({"file": "a.xls", "status": "imported", "expected_match": True})
    summary = session.summary()
    assert summary["imported"] == 1
    assert session.is_passing() is True


def test_successful_xls_open_binds_loaded_path_and_real_data(qtbot) -> None:
    """An empty fallback workbook must not count as a successful XLS import."""
    sample = Path("tests/docs/excel/xls/libreoffice__AutoFilter.xls").resolve()
    win = LedgerWindow()
    qtbot.addWidget(win)
    win.maybe_save_prompt = lambda: True

    assert win.open_file(sample) is True
    assert Path(win.current_file_path).resolve() == sample
    assert win.is_read_only_import is True
    wb = win.spreadsheet_view.workbook
    assert len(wb.sheets) == 3
    assert any(sheet.cells for sheet in wb.sheets)


def test_corrupt_xls_open_is_handled_without_binding_path(qtbot, monkeypatch) -> None:
    dialogs: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "critical", lambda parent, title, text, *a, **kw: dialogs.append(text)
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda parent, title, text, *a, **kw: dialogs.append(text)
    )
    win = LedgerWindow()
    qtbot.addWidget(win)
    win.maybe_save_prompt = lambda: True

    sample = Path("tests/docs/excel/xls/libreoffice__crash-5.xls").resolve()
    assert win.open_file(sample) is False
    assert win.current_file_path is None
    assert len(dialogs) == 1
