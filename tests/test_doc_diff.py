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

from scripts.office_diff.capture import (
    CDP_CANVAS_RECTS,
    align_pixmap_to_canvas,
    resolve_canvas_target,
)
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


def test_diff_result_foreground_fields_serialization():
    dr = DiffResult(
        file="sample.docx",
        app="word",
        similarity=0.96,
        mae=2.5,
        edge_similarity=0.98,
        roi_similarity=0.97,
        category="CRITICAL_MISMATCH",
        orig_size=(1178, 767),
        target_size=(1178, 767),
        foreground_score=0.45,
        recall=0.45,
        precision=0.90,
        color_hist_similarity=0.80,
        tier="CRITICAL_MISMATCH",
    )
    d = dr.to_dict()
    assert d["foreground_score"] == 0.45
    assert d["recall"] == 0.45
    assert d["precision"] == 0.9
    assert d["color_hist_similarity"] == 0.8
    assert d["tier"] == "CRITICAL_MISMATCH"
    assert d["pixel_similarity"] == 0.96


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


def test_align_pixmap_to_canvas():
    from PySide6.QtGui import QColor, QPixmap

    # 1. Pixmap larger than target
    src = QPixmap(1440, 900)
    src.fill(QColor("blue"))
    aligned = align_pixmap_to_canvas(src, (1178, 798))
    assert aligned.width() == 1178
    assert aligned.height() == 798

    # 2. Pixmap smaller than target
    src_small = QPixmap(500, 400)
    src_small.fill(QColor("green"))
    aligned_small = align_pixmap_to_canvas(src_small, (982, 745))
    assert aligned_small.width() == 982
    assert aligned_small.height() == 745

    # 3. Already matching size
    src_exact = QPixmap(1178, 767)
    aligned_exact = align_pixmap_to_canvas(src_exact, (1178, 767))
    assert aligned_exact.width() == 1178
    assert aligned_exact.height() == 767


def test_cdp_canvas_rects_and_viewport_isolation():
    assert CDP_CANVAS_RECTS["excel"] == (1178, 798)
    assert CDP_CANVAS_RECTS["powerpoint"] == (982, 745)
    assert CDP_CANVAS_RECTS["word"] == (1178, 767)

    class DummyWindow:
        def centralWidget(self):
            return "central_widget"

    w = DummyWindow()
    assert resolve_canvas_target(w, "word") == "central_widget"
    assert resolve_canvas_target(w, "excel") == "central_widget"
    assert resolve_canvas_target(w, "powerpoint") == "central_widget"


def test_filled_rectangle_vs_blank_below_cosmetic_minor(tmp_path):
    from PySide6.QtGui import QPainter

    p1 = tmp_path / "base_rect.png"
    p2 = tmp_path / "cand_blank.png"

    img1 = QImage(320, 240, QImage.Format.Format_ARGB32)
    img1.fill(QColor("white"))
    painter = QPainter(img1)
    painter.fillRect(100, 80, 40, 30, QColor("#1F4E79"))
    painter.end()
    img1.save(str(p1))

    img2 = QImage(320, 240, QImage.Format.Format_ARGB32)
    img2.fill(QColor("white"))
    img2.save(str(p2))

    res = compare_canvases(p1, p2, app="powerpoint")
    assert res.foreground_score is not None
    assert res.foreground_score < 0.85
    assert res.category == "CRITICAL_MISMATCH"
    assert res.tier == "CRITICAL_MISMATCH"


def test_blank_pair_scores_100_without_zero_division(tmp_path):
    p1 = tmp_path / "blank1.png"
    p2 = tmp_path / "blank2.png"
    for p in (p1, p2):
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        img.fill(QColor("white"))
        img.save(str(p))

    res = compare_canvases(p1, p2, app="word")
    assert res.foreground_score == 1.0
    assert res.recall == 1.0
    assert res.precision == 1.0
    assert res.color_hist_similarity == 1.0
    assert res.category == "PARITY_MATCH"


def test_dark_background_slide_detection_and_missing_fill(tmp_path):
    from PySide6.QtGui import QPainter

    p1 = tmp_path / "dark_base.png"
    p2 = tmp_path / "dark_cand_same.png"
    p3 = tmp_path / "white_cand_wrong_bg.png"
    p4 = tmp_path / "dark_cand_wrong_color.png"

    def make_slide(path: Path, bg: QColor, fg: QColor | None) -> None:
        img = QImage(240, 180, QImage.Format.Format_ARGB32)
        img.fill(bg)
        if fg is not None:
            painter = QPainter(img)
            painter.fillRect(60, 50, 80, 40, fg)
            painter.end()
        img.save(str(path))

    make_slide(p1, QColor("#1E1E2E"), QColor("#FFFFFF"))
    make_slide(p2, QColor("#1E1E2E"), QColor("#FFFFFF"))
    make_slide(p3, QColor("#FFFFFF"), QColor("#FF0000"))
    make_slide(p4, QColor("#1E1E2E"), QColor("#FF0000"))

    res_match = compare_canvases(p1, p2, app="powerpoint")
    assert res_match.foreground_score == 1.0
    assert res_match.category == "PARITY_MATCH"

    res_wrong_bg = compare_canvases(p1, p3, app="powerpoint")
    assert res_wrong_bg.foreground_score is not None
    assert res_wrong_bg.foreground_score < 0.70
    assert res_wrong_bg.category == "CRITICAL_MISMATCH"

    res_wrong_color = compare_canvases(p1, p4, app="powerpoint")
    assert res_wrong_color.recall == 1.0
    assert res_wrong_color.precision == 1.0
    assert res_wrong_color.color_hist_similarity == 0.0
    assert res_wrong_color.category == "CRITICAL_MISMATCH"


def test_antialias_dilation_tolerance(tmp_path):
    from PySide6.QtGui import QPainter

    p1 = tmp_path / "shift_a.png"
    p2 = tmp_path / "shift_b.png"

    for p, dx in ((p1, 0), (p2, 2)):
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        img.fill(QColor("white"))
        painter = QPainter(img)
        painter.fillRect(50 + dx, 50, 60, 20, QColor("black"))
        painter.end()
        img.save(str(p))

    res = compare_canvases(p1, p2, app="word")
    assert res.foreground_score is not None
    assert res.foreground_score >= 0.95
    assert res.category == "PARITY_MATCH"

