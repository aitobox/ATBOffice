"""Unit and integration tests for office document visual diff tooling."""
# ruff: noqa: E402, E501

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.office_diff.comparator import classify_similarity, compare_canvases, is_blank_canvas
from scripts.office_diff.corpus import load_expectations, partition_corpus
from scripts.office_diff.models import CaptureResult, DiffResult, DocumentTarget
from scripts.office_diff.reporter import generate_report


def test_corpus_partitioning():
    docs_root = REPO_ROOT / "tests" / "docs"
    exp_file = docs_root / "expectations.json"
    assert exp_file.exists(), "tests/docs/expectations.json must exist"

    expectations = load_expectations(exp_file)
    assert len(expectations) == 150, f"Expected 150 items in corpus, got {len(expectations)}"

    supported, unsupported = partition_corpus(expectations, docs_root)
    assert len(supported) == 73, f"Expected 73 core supported OOXML items, got {len(supported)}"
    assert len(unsupported) == 77, f"Expected 77 unsupported/legacy items, got {len(unsupported)}"

    for target in supported:
        assert target.is_supported is True
        assert target.expected_status == "ok"
        assert target.format in ("docx", "xlsx", "pptx", "xlsm", "docm", "pptm")
        assert target.app in ("word", "excel", "powerpoint")


def test_models_serialization():
    dt = DocumentTarget(
        file="test.docx",
        path=Path("/tmp/test.docx"),
        format="docx",
        app="word",
        expected_status="ok",
        is_supported=True,
    )
    d_dict = dt.to_dict()
    assert d_dict["file"] == "test.docx"
    assert d_dict["path"] == "/tmp/test.docx"

    cr = CaptureResult(
        file="test.docx",
        app="word",
        status="captured",
        screenshot_path="/tmp/test.png",
        width=1440,
        height=900,
    )
    c_dict = cr.to_dict()
    assert c_dict["status"] == "captured"
    assert c_dict["width"] == 1440

    dr = DiffResult(
        file="test.docx",
        app="word",
        similarity=0.98,
        mae=2.5,
        edge_similarity=0.99,
        roi_similarity=0.97,
        category="PARITY_MATCH",
        orig_size=(1440, 900),
        target_size=(1440, 900),
    )
    r_dict = dr.to_dict()
    assert r_dict["category"] == "PARITY_MATCH"
    assert r_dict["similarity"] == 0.98


def test_classify_similarity():
    assert classify_similarity(0.96) == "PARITY_MATCH"
    assert classify_similarity(0.90) == "COSMETIC_MINOR"
    assert classify_similarity(0.75) == "LAYOUT_DRIFT"
    assert classify_similarity(0.50) == "CRITICAL_MISMATCH"
    assert classify_similarity(None) == "UNVERIFIED"
    assert classify_similarity(0.95, override="CUSTOM") == "CUSTOM"


def test_compare_identical_canvases():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        p1 = tmp_path / "img1.png"
        p2 = tmp_path / "img2.png"
        diff_out = tmp_path / "diff.png"

        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        img.fill(QColor("lightblue"))
        img.save(str(p1))
        img.save(str(p2))

        res = compare_canvases(p1, p2, app="word", diff_out=diff_out)
        assert res.category == "PARITY_MATCH"
        assert res.similarity is not None
        assert pytest.approx(res.similarity, 0.001) == 1.0
        assert pytest.approx(res.mae, 0.001) == 0.0
        assert diff_out.exists()


def test_compare_different_canvases():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        p1 = tmp_path / "img1.png"
        p2 = tmp_path / "img2.png"

        img1 = QImage(200, 200, QImage.Format.Format_ARGB32)
        img1.fill(QColor("white"))
        img1.save(str(p1))

        img2 = QImage(200, 200, QImage.Format.Format_ARGB32)
        img2.fill(QColor("black"))
        img2.save(str(p2))

        res = compare_canvases(p1, p2, app="word")
        assert res.similarity is not None
        assert res.similarity < 0.5
        assert res.category == "CRITICAL_MISMATCH"


def test_strict_size_mismatch_guardrail():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        p1 = tmp_path / "vibe.png"
        p2 = tmp_path / "atb.png"

        img1 = QImage(1178, 767, QImage.Format.Format_ARGB32)
        img1.fill(QColor("white"))
        img1.save(str(p1))

        img2 = QImage(1440, 773, QImage.Format.Format_ARGB32)
        img2.fill(QColor("white"))
        img2.save(str(p2))

        # Default strict mode: must return INCOMPARABLE_SIZE with similarity=None
        res = compare_canvases(p1, p2, app="word", normalize_size=False)
        assert res.category == "INCOMPARABLE_SIZE"
        assert res.similarity is None
        assert res.orig_size == (1178, 767)
        assert res.target_size == (1440, 773)

        # Normalized mode: permits approximate scaled comparison
        res_norm = compare_canvases(p1, p2, app="word", normalize_size=True)
        assert res_norm.normalized is True
        assert res_norm.similarity is not None


def test_compare_missing_canvas():
    p1 = Path("/tmp/nonexistent_orig.png")
    p2 = Path("/tmp/nonexistent_target.png")
    res = compare_canvases(p1, p2, app="excel")
    assert res.category == "MISSING"
    assert res.similarity is None


def test_is_blank_canvas():
    img_blank = QImage(100, 100, QImage.Format.Format_ARGB32)
    img_blank.fill(QColor("white"))
    assert is_blank_canvas(img_blank) is True

    img_content = QImage(100, 100, QImage.Format.Format_ARGB32)
    img_content.fill(QColor("white"))
    for i in range(10):
        img_content.setPixelColor(i * 10, i * 10, QColor(i * 20, 100, 150))
    assert is_blank_canvas(img_content) is False


def test_generate_report_and_task_card():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "OFFICE_DOCS_DIFF.md"
        results = [
            DiffResult(
                file="libreoffice__A019_min.docx",
                app="word",
                similarity=0.96,
                mae=2.1,
                edge_similarity=0.98,
                roi_similarity=0.97,
                category="PARITY_MATCH",
                orig_size=(1440, 900),
                target_size=(1440, 900),
            ),
            DiffResult(
                file="libreoffice__totalsRow.xlsx",
                app="excel",
                similarity=0.72,
                mae=28.4,
                edge_similarity=0.75,
                roi_similarity=0.70,
                category="LAYOUT_DRIFT",
                orig_size=(1440, 900),
                target_size=(1440, 900),
            ),
            DiffResult(
                file="mismatched.pptx",
                app="powerpoint",
                similarity=None,
                mae=255.0,
                edge_similarity=0.0,
                roi_similarity=0.0,
                category="INCOMPARABLE_SIZE",
                orig_size=(1178, 767),
                target_size=(1440, 773),
            ),
        ]

        content = generate_report(results, out_file)
        assert out_file.exists()
        assert "Parity Report" in content
        assert "libreoffice__A019_min.docx" in content
        assert "PARITY_MATCH" in content
        assert "INCOMPARABLE_SIZE" in content
        assert "TASK-DOC-01" in content


def test_run_office_diff_cli_dry_run():
    script_path = REPO_ROOT / "scripts" / "run_office_diff.py"
    res = subprocess.run(
        [sys.executable, str(script_path), "--dry-run"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "73 supported OOXML" in res.stdout
    assert "Active targets: 73" in res.stdout
