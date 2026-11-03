#!/usr/bin/env python3
"""Phase 7 Capture Contract and Baseline Verification Tests (TASK-701 / Issue #235).

Verifies:
1. 412 screenshot control matrix completeness and schema against records.json.
2. Explicit capture scenario registry with strict non-fallback error handling.
3. Duplicate screenshot hash collision detection.
4. Accurate metric separation in imgdiff (Pixel MAE vs ROI/Structural similarity).
5. ScreenCaptureManager strict rejection of silent fallbacks and invalid tab indices.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage, QPainter

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))


class TestControlMatrix:
    """Verifies docs/clone/phase7_control_matrix.csv adherence to contract."""

    def test_control_matrix_completeness_and_schema(self):
        matrix_path = REPO_ROOT / "docs" / "clone" / "phase7_control_matrix.csv"
        records_path = REPO_ROOT / ".vibeoffice" / "screenshots" / "records.json"

        assert matrix_path.exists(), f"Control matrix missing: {matrix_path}"

        with open(matrix_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            matrix_rows = list(reader)

        expected_headers = [
            "id",
            "module",
            "original_ref",
            "target_ref",
            "context",
            "command_id",
            "visual_status",
            "behavior_status",
            "test",
            "evidence",
        ]
        assert reader.fieldnames == expected_headers, (
            f"Matrix header mismatch. Expected {expected_headers}, got {reader.fieldnames}"
        )

        assert len(matrix_rows) == 412, (
            f"Control matrix must contain exactly 412 rows, found {len(matrix_rows)}"
        )

        valid_statuses = {"verified", "partial", "missing", "unverified"}
        matrix_orig_refs = set()

        for idx, row in enumerate(matrix_rows, 1):
            assert row["id"], f"Row {idx} missing id"
            assert row["module"] in {
                "00_start_center",
                "01_quire",
                "02_ledger",
                "03_lectern",
            }, f"Row {idx} invalid module: {row['module']}"
            assert row["original_ref"], f"Row {idx} missing original_ref"
            assert row["visual_status"] in valid_statuses, (
                f"Row {idx} invalid visual_status: {row['visual_status']}"
            )
            assert row["behavior_status"] in valid_statuses, (
                f"Row {idx} invalid behavior_status: {row['behavior_status']}"
            )
            matrix_orig_refs.add(row["original_ref"])

        assert len(matrix_orig_refs) == 412, "All 412 original_refs in matrix must be unique"

        # Check 1:1 correspondence with records.json if present
        if records_path.exists():
            with open(records_path, encoding="utf-8") as f:
                records = json.load(f)
            assert len(records) == 412, (
                f"Expected 412 records in records.json, found {len(records)}"
            )
            expected_orig_refs = {r["path"] for r in records}
            missing_in_matrix = expected_orig_refs - matrix_orig_refs
            assert not missing_in_matrix, (
                f"Control matrix missing {len(missing_in_matrix)} records: "
                f"{list(missing_in_matrix)[:5]}"
            )


class TestCaptureScenarioRegistry:
    """Verifies scripts/phase7_capture_scenarios.py scenario contracts."""

    def test_scenario_registry_no_silent_fallback(self):
        from phase7_capture_scenarios import (
            CaptureScenario,
            CaptureScenarioRegistry,
            ScenarioCaptureError,
            ScenarioStatus,
        )

        registry = CaptureScenarioRegistry()
        assert len(registry.all_scenarios()) == 412, "Registry must load all 412 scenarios"

        failing_scenario = CaptureScenario(
            id=9999,
            module="01_quire",
            filename="non_existent_target.png",
            category="dialog",
            gui_target="NonExistentDialog",
            action="Trigger non-existent dialog",
            status=ScenarioStatus.MISSING,
        )

        with pytest.raises(ScenarioCaptureError):
            registry.execute_scenario(failing_scenario, app_context=None, strict=True)

    def test_duplicate_hash_tracker(self):
        from phase7_capture_scenarios import DuplicateHashTracker

        tracker = DuplicateHashTracker()
        img1 = QImage(100, 100, QImage.Format.Format_RGB32)
        img1.fill(QColor(255, 0, 0))

        img2 = QImage(100, 100, QImage.Format.Format_RGB32)
        img2.fill(QColor(255, 0, 0))

        img3 = QImage(100, 100, QImage.Format.Format_RGB32)
        img3.fill(QColor(0, 255, 0))

        h1 = tracker.register_image("01_quire/rec1.png", img1)
        assert h1

        h2 = tracker.register_image("01_quire/rec2.png", img2)
        assert h1 == h2
        duplicates = tracker.get_duplicates()
        assert h1 in duplicates
        assert set(duplicates[h1]) == {"01_quire/rec1.png", "01_quire/rec2.png"}

        h3 = tracker.register_image("01_quire/rec3.png", img3)
        assert h3 != h1

    def test_capture_manager_strict_mode_rejects_missing(self, tmp_path):
        from capture_atboffice_screens import ScreenCaptureManager
        from phase7_capture_scenarios import ScenarioCaptureError

        mgr = ScreenCaptureManager(tmp_path, strict=True)
        missing_rec = {
            "module": "01_quire",
            "filename": "999_dialog_NonExistent__Dialog.png",
            "category": "dialog",
            "path": "01_quire/999_dialog_NonExistent__Dialog.png",
        }
        with pytest.raises(ScenarioCaptureError):
            mgr.capture_record(missing_rec)

    def test_capture_manager_strict_mode_rejects_invalid_tab(self, tmp_path):
        from capture_atboffice_screens import ScreenCaptureManager
        from phase7_capture_scenarios import ScenarioCaptureError

        mgr = ScreenCaptureManager(tmp_path, strict=True)
        # FontDialog in Quire has at most 3 tabs; tab99 must fail in strict mode
        invalid_tab_rec = {
            "module": "01_quire",
            "filename": "011_dialog_Font__Font_tab99_Invalid.png",
            "category": "dialog",
            "path": "01_quire/011_dialog_Font__Font_tab99_Invalid.png",
        }
        with pytest.raises(ScenarioCaptureError):
            mgr.capture_record(invalid_tab_rec)


class TestImgdiffMetricSeparation:
    """Verifies scripts/imgdiff.py correctly separates MAE and ROI metrics."""

    def test_imgdiff_metric_distinction(self, tmp_path):
        from imgdiff import compare_images, generate_report

        img_a = QImage(320, 200, QImage.Format.Format_RGB32)
        img_a.fill(QColor(255, 255, 255))

        img_b = QImage(320, 200, QImage.Format.Format_RGB32)
        img_b.fill(QColor(255, 255, 255))
        painter = QPainter(img_b)
        painter.fillRect(110, 50, 100, 100, QColor(0, 0, 0))
        painter.end()

        path_a = tmp_path / "img_a.png"
        path_b = tmp_path / "img_b.png"
        img_a.save(str(path_a), "PNG")
        img_b.save(str(path_b), "PNG")

        result = compare_images(path_a, path_b)

        assert hasattr(result, "pixel_mae_similarity"), "Missing pixel_mae_similarity attribute"
        assert hasattr(result, "roi_similarity"), "Missing roi_similarity attribute"
        assert result.pixel_mae_similarity > 0.8, "Whole image similarity should be high"
        assert result.roi_similarity < result.pixel_mae_similarity, (
            "Central ROI similarity should be significantly lower than full image"
        )

        report = generate_report([result])
        assert "Pixel MAE" in report or "pixel_mae" in report.lower(), (
            "Report should state Pixel MAE"
        )
        assert "MAE as SSIM" not in report
