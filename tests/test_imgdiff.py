"""Unit tests for scripts/imgdiff.py visual similarity tool."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

from scripts.imgdiff import DiffResult, compare_images, generate_report


def test_compare_identical_images():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        p1 = tmp_path / "img1.png"
        p2 = tmp_path / "img2.png"

        # Create identical 100x100 white squares
        img = QImage(100, 100, QImage.Format.Format_RGB888)
        img.fill(QColor("white"))
        img.save(str(p1))
        img.save(str(p2))

        res = compare_images(p1, p2, threshold=0.9)
        assert res.passed is True
        assert pytest.approx(res.similarity, 0.001) == 1.0


def test_compare_different_images():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        p1 = tmp_path / "white.png"
        p2 = tmp_path / "black.png"

        img_w = QImage(100, 100, QImage.Format.Format_RGB888)
        img_w.fill(QColor("white"))
        img_w.save(str(p1))

        img_b = QImage(100, 100, QImage.Format.Format_RGB888)
        img_b.fill(QColor("black"))
        img_b.save(str(p2))

        res = compare_images(p1, p2, threshold=0.9)
        assert res.passed is False
        assert pytest.approx(res.similarity, 0.001) == 0.0


def test_generate_report():
    with tempfile.TemporaryDirectory() as tmpdir:
        report_file = Path(tmpdir) / "REPORT.md"
        results = [
            DiffResult(
                module="01_quire",
                filename="test1.png",
                similarity=0.95,
                passed=True,
                atb_size=(100, 100),
                orig_size=(100, 100),
            ),
            DiffResult(
                module="01_quire",
                filename="test2.png",
                similarity=0.70,
                passed=False,
                atb_size=(100, 100),
                orig_size=(100, 100),
            ),
        ]
        report = generate_report(results, threshold=0.85)
        report_file.write_text(report, encoding="utf-8")

        assert "# ATBOffice vs. VibeOffice UI 图像差异对比报告" in report
        assert "01_quire" in report
        assert "test1.png" in report
        assert "test2.png" in report
        assert "95.00%" in report
        assert "70.00%" in report
