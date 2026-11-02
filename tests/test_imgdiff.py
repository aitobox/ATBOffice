"""Unit tests for scripts/imgdiff.py visual similarity tool."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from scripts.imgdiff import DiffResult, compare_images, generate_report


def test_compare_identical_images():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        p1 = tmp_path / "img1.png"
        p2 = tmp_path / "img2.png"

        # Create identical 100x100 white squares
        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        img.save(p1)
        img.save(p2)

        res = compare_images(p1, p2, threshold=0.9)
        assert res.passed is True
        assert pytest.approx(res.similarity, 0.001) == 1.0


def test_compare_different_images():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        p1 = tmp_path / "white.png"
        p2 = tmp_path / "black.png"

        img_w = Image.new("RGB", (100, 100), color=(255, 255, 255))
        img_b = Image.new("RGB", (100, 100), color=(0, 0, 0))
        img_w.save(p1)
        img_b.save(p2)

        res = compare_images(p1, p2, threshold=0.9)
        assert res.passed is False
        assert pytest.approx(res.similarity, 0.001) == 0.0


def test_generate_report():
    with tempfile.TemporaryDirectory() as tmpdir:
        report_file = Path(tmpdir) / "REPORT.md"
        results = [
            DiffResult(
                module="00_start_center",
                filename="test1.png",
                similarity=0.95,
                passed=True,
                atb_size=(1440, 900),
                orig_size=(1440, 900),
            ),
            DiffResult(
                module="01_quire",
                filename="test2.png",
                similarity=0.82,
                passed=False,
                atb_size=(1440, 900),
                orig_size=(1440, 900),
            ),
        ]
        generate_report(results, threshold=0.9, report_path=report_file)
        assert report_file.exists()
        content = report_file.read_text(encoding="utf-8")
        assert "ATBOffice vs. VibeOffice UI 图像差异对比报告" in content
        assert "00_start_center" in content
        assert "01_quire" in content
        assert "95.00%" in content
