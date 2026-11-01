# tests/test_diagnostics.py
"""Unit tests for ATBOffice crash diagnostics and telemetry."""

from __future__ import annotations

import sys
from pathlib import Path

from atboffice.core.diagnostics import (
    CrashDiagnostics,
    get_environment_telemetry,
    sanitize_traceback,
)


def test_get_environment_telemetry():
    telemetry = get_environment_telemetry()
    assert isinstance(telemetry, dict)
    assert "python_version" in telemetry
    assert "platform" in telemetry
    assert "machine" in telemetry
    assert "pyside_version" in telemetry
    assert "qt_version" in telemetry
    assert "clone_sha" in telemetry
    assert "orig_sha" in telemetry
    assert "crash_report_dir" in telemetry

    # Verify versions are non-empty strings
    assert len(telemetry["python_version"]) > 0
    assert len(telemetry["platform"]) > 0
    assert len(telemetry["pyside_version"]) > 0


def test_sanitize_traceback_removes_sensitive_document_content():
    raw_traceback = (
        'Traceback (most recent call last):\n'
        '  File "/path/to/atboffice/modules/writer/views/editor.py", line 42, in insert_text\n'
        '    doc.insert("CONFIDENTIAL_FINANCIAL_REPORT_2026_Q3")\n'
        'ValueError: Document string payload corrupted: CONFIDENTIAL_FINANCIAL_REPORT_2026_Q3\n'
    )
    sanitized = sanitize_traceback(raw_traceback)
    assert "/path/to/atboffice/modules/writer/views/editor.py" in sanitized
    assert "line 42" in sanitized
    assert "insert_text" in sanitized
    assert "ValueError" in sanitized
    # Sensitive document text payload must be sanitized/redacted
    assert "CONFIDENTIAL_FINANCIAL_REPORT_2026_Q3" not in sanitized


def test_crash_diagnostics_enable_and_disable(tmp_path: Path):
    diag_log = tmp_path / "crash_test.log"
    diagnostics = CrashDiagnostics(log_path=diag_log)

    original_excepthook = sys.excepthook
    try:
        diagnostics.enable()
        assert sys.excepthook != original_excepthook

        # Simulate uncaught exception
        try:
            raise RuntimeError("Test diagnostic error")
        except RuntimeError:
            sys.excepthook(*sys.exc_info())

        assert diag_log.exists()
        log_content = diag_log.read_text(encoding="utf-8")
        assert "RuntimeError" in log_content
        assert "Test diagnostic error" in log_content
        assert "Environment Telemetry" in log_content
    finally:
        diagnostics.disable()
        assert sys.excepthook == original_excepthook


def test_crash_diagnostics_find_reports(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "atboffice.core.diagnostics._get_platform_crash_dir",
        lambda: tmp_path,
    )
    diagnostics = CrashDiagnostics()
    # Create dummy crash report
    report_file = tmp_path / "atboffice_2026-11-01-crash.ips"
    report_file.write_text("dummy crash report")

    reports = diagnostics.find_recent_crash_reports()
    assert len(reports) == 1
    assert reports[0].name == "atboffice_2026-11-01-crash.ips"
