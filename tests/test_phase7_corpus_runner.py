"""Phase 7 Corpus Audit Runner & Multi-Process Isolated Contract Tests.

Verifies:
1. Complete 150/150 inventory and hash integrity in tests/docs/expectations.json.
2. Isolated process runner enforcing 30s hard timeout (with process termination/recovery).
3. Independent classification of timeout, crash, fail, and loss under fault injection.
4. Multi-stage execution (parse, model, render, roundtrip) without unhandled Qt exceptions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atboffice.deep.audit.core import (
    AuditSession,
    CorpusExpectations,
    IsolatedFileRunner,
    audit_corpus_file,
)


def test_expectations_manifest_completeness() -> None:
    """Validate that expectations.json contains all 150 curated documents with valid SHA-256."""
    exp_path = Path("tests/docs/expectations.json")
    assert exp_path.exists(), "tests/docs/expectations.json must exist"

    manifest = CorpusExpectations(exp_path)
    assert len(manifest) == 150, f"Expected exactly 150 files in manifest, got {len(manifest)}"

    categories = manifest.category_counts()
    assert categories.get("valid", 0) == 73, f"Expected 73 valid files, got {categories.get('valid')}"
    assert categories.get("encrypted", 0) == 1, f"Expected 1 encrypted file, got {categories.get('encrypted')}"
    assert categories.get("corrupt", 0) == 1, f"Expected 1 corrupt file, got {categories.get('corrupt')}"
    assert categories.get("unsupported_format", 0) == 75, (
        f"Expected 75 unsupported_format files, got {categories.get('unsupported_format')}"
    )

    # Verify SHA-256 for all 150 files on disk
    mismatches = manifest.verify_on_disk_hashes()
    assert not mismatches, f"Hash mismatches or missing files: {mismatches}"


def test_runner_isolated_timeout_injection() -> None:
    """Verify that a hanging worker is forcefully terminated within timeout and returns status='timeout'."""
    runner = IsolatedFileRunner(timeout=1.0)
    result = runner.run_with_injection(
        file_path="tests/docs/word/docx/libreoffice__A019_min.docx",
        fault="hang",
    )
    assert result["status"] == "timeout"
    assert "timeout" in result.get("reason", "").lower()
    assert result.get("terminated") is True


def test_runner_isolated_crash_injection() -> None:
    """Verify that a worker that crashes/aborts is captured as status='crash'."""
    runner = IsolatedFileRunner(timeout=5.0)
    result = runner.run_with_injection(
        file_path="tests/docs/word/docx/libreoffice__A019_min.docx",
        fault="crash",
    )
    assert result["status"] == "crash"
    assert result.get("exitcode") is not None
    assert result["exitcode"] != 0


def test_runner_isolated_fail_injection() -> None:
    """Verify that an unexpected parse/model exception on a valid file returns status='fail'."""
    runner = IsolatedFileRunner(timeout=5.0)
    result = runner.run_with_injection(
        file_path="tests/docs/word/docx/libreoffice__A019_min.docx",
        fault="exception",
    )
    assert result["status"] == "fail"
    assert "injected error" in result.get("reason", "").lower()


def test_runner_isolated_loss_injection() -> None:
    """Verify that feature loss during roundtrip returns status='loss'."""
    runner = IsolatedFileRunner(timeout=5.0)
    result = runner.run_with_injection(
        file_path="tests/docs/word/docx/libreoffice__A019_min.docx",
        fault="loss",
    )
    assert result["status"] == "loss"
    assert "feature_losses" in result
    assert len(result["feature_losses"]) > 0


def test_runner_valid_ooxml_stages() -> None:
    """Verify that valid OOXML files execute parse, model, render, and roundtrip stages."""
    sample_files = [
        "tests/docs/word/docx/libreoffice__A019_min.docx",
        "tests/docs/excel/xlsx/libreoffice__empty.xlsx",
        "tests/docs/powerpoint/pptx/libreoffice__smartart-text.pptx",
    ]
    manifest = CorpusExpectations(Path("tests/docs/expectations.json"))

    for file_str in sample_files:
        res = audit_corpus_file(file_str, expectations=manifest, timeout=10.0)
        assert res["status"] == "ok", f"Expected 'ok' for {file_str}, got {res}"
        stages = res.get("stages", {})
        assert stages.get("parse") == "ok"
        assert stages.get("model") == "ok"
        assert stages.get("render") == "ok"
        assert stages.get("roundtrip") == "ok"
        assert res.get("expected_match") is True


def test_runner_encrypted_detection() -> None:
    """Verify that encrypted OOXML is detected and matched as expected encrypted rejection."""
    manifest = CorpusExpectations(Path("tests/docs/expectations.json"))
    res = audit_corpus_file(
        "tests/docs/word/docx/poi__protected_agile.docx",
        expectations=manifest,
        timeout=10.0,
    )
    assert res["status"] == "encrypted"
    assert res.get("expected_match") is True
    assert res.get("stages", {}).get("parse") == "rejected_encrypted"


def test_runner_corrupt_rejection() -> None:
    """Verify that corrupt archive is rejected and matched as expected corrupt file."""
    manifest = CorpusExpectations(Path("tests/docs/expectations.json"))
    res = audit_corpus_file(
        "tests/docs/excel/xlsx/poi__clusterfuzz-testcase-minimized-XLSX2CSVFuzzer-5636439151607808.xlsx",
        expectations=manifest,
        timeout=10.0,
    )
    assert res["status"] == "corrupt"
    assert res.get("expected_match") is True
    assert res.get("stages", {}).get("parse") == "rejected_corrupt"


def test_runner_legacy_binary_rejection_no_fake_compat() -> None:
    """Verify that legacy binary files (.doc, .xls, .ppt) are marked unsupported_format."""
    manifest = CorpusExpectations(Path("tests/docs/expectations.json"))
    samples = [
        "tests/docs/word/doc/libreoffice__cp1000044.doc",
        "tests/docs/excel/xls/libreoffice__AutoFilter.xls",
        "tests/docs/powerpoint/ppt/libreoffice__tdf157636.ppt",
    ]
    for s in samples:
        res = audit_corpus_file(s, expectations=manifest, timeout=10.0)
        assert res["status"] == "unsupported_format"
        assert res.get("expected_match") is True
        assert res.get("stages", {}).get("parse") == "rejected_unsupported_format"


def test_audit_session_accounting() -> None:
    """Verify AuditSession accounts for all categories and evaluates passing condition."""
    session = AuditSession()
    session.record_result({"file": "a.docx", "status": "ok", "expected_match": True})
    session.record_result({"file": "b.docx", "status": "encrypted", "expected_match": True})
    session.record_result({"file": "c.doc", "status": "unsupported_format", "expected_match": True})
    session.record_result({"file": "d.xlsx", "status": "corrupt", "expected_match": True})

    summary = session.summary()
    assert summary["attempted"] == 4
    assert summary["ok"] == 1
    assert summary["encrypted"] == 1
    assert summary["unsupported_format"] == 1
    assert summary["corrupt"] == 1
    assert summary["timeout"] == 0
    assert summary["crash"] == 0
    assert summary["fail"] == 0
    assert summary["loss"] == 0
    assert session.is_passing() is True

    # Inject unmatched failure
    session.record_result({"file": "e.docx", "status": "fail", "expected_match": False, "reason": "broken"})
    assert session.is_passing() is False
