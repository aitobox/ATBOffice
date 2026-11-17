"""Tests for shared capture regions (issue #359): both engines capture the same region."""
# ruff: noqa: E402

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT / "src", REPO_ROOT):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from scripts.office_diff.regions import (
    MANIFEST_NAME,
    baseline_region,
    baseline_target_size,
    default_region,
    load_regions,
    region_names,
)

EXCEL_FIXTURE = REPO_ROOT / "tests" / "docs" / "excel" / "xlsx" / "libreoffice__Pivot2_Row.xlsx"


def _write_manifest(directory: Path, entries: list[dict]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / MANIFEST_NAME).write_text(json.dumps(entries), encoding="utf-8")


def _write_png(path: Path, size: tuple[int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "white").save(path)


def test_region_table_defines_both_regions_for_every_app():
    table = load_regions()
    assert default_region() == "canvas"
    assert region_names() == ["canvas", "workspace"]
    for app in ("word", "excel", "powerpoint"):
        for region in ("canvas", "workspace"):
            spec = table["regions"][app][region]
            assert spec["selector"].startswith("#")
            assert spec["box"] in ("client", "border")


def test_baseline_size_prefers_manifest_with_matching_region(tmp_path):
    _write_png(tmp_path / "excel" / "a.xlsx.png", (10, 10))
    _write_manifest(
        tmp_path,
        [{"file": "a.xlsx", "status": "captured", "region": "canvas", "width": 1100, "height": 700}],
    )
    assert baseline_target_size(tmp_path, "excel", "a.xlsx", "canvas") == (1100, 700)
    # A different region in the baseline means its size says nothing about ours.
    assert baseline_target_size(tmp_path, "excel", "a.xlsx", "workspace") is None
    assert baseline_region(tmp_path) == "canvas"


def test_legacy_manifest_without_region_is_workspace(tmp_path):
    _write_png(tmp_path / "excel" / "a.xlsx.png", (1178, 798))
    _write_manifest(tmp_path, [{"file": "a.xlsx", "status": "captured", "clip": {}}])
    assert baseline_region(tmp_path) == "workspace"
    assert baseline_target_size(tmp_path, "excel", "a.xlsx", "workspace") == (1178, 798)
    assert baseline_target_size(tmp_path, "excel", "a.xlsx", "canvas") is None


def test_baseline_size_falls_back_to_png_and_handles_missing(tmp_path):
    _write_png(tmp_path / "word" / "b.docx.png", (640, 480))
    assert baseline_target_size(tmp_path, "word", "b.docx", "canvas") == (640, 480)
    assert baseline_target_size(tmp_path, "word", "missing.docx", "canvas") is None
    assert baseline_target_size(None, "word", "b.docx", "canvas") is None
    assert baseline_region(tmp_path) is None


def test_no_hard_coded_audit_paths():
    res = subprocess.run(
        ["grep", "-rI", "--exclude-dir=__pycache__", "office_audit_20261106", "scripts/", ".agents/"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert res.stdout == ""


@pytest.mark.skipif(not EXCEL_FIXTURE.exists(), reason="Excel fixture missing")
def test_excel_workspace_capture_includes_tab_strip_without_white_band(tmp_path):
    from scripts.office_diff.models import DocumentTarget
    from scripts.run_office_diff import run_diff_suite

    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    size = (1178, 798)
    _write_png(baseline / "excel" / f"{EXCEL_FIXTURE.name}.png", size)
    _write_manifest(
        baseline,
        [{"file": EXCEL_FIXTURE.name, "status": "captured", "region": "workspace", "width": size[0], "height": size[1]}],
    )
    target = DocumentTarget(
        file=EXCEL_FIXTURE.name,
        path=EXCEL_FIXTURE,
        format="xlsx",
        app="excel",
        expected_status="ok",
        is_supported=True,
    )

    run_diff_suite(
        targets=[target],
        baseline_dir=baseline,
        candidate_dir=candidate,
        diff_dir=tmp_path / "diff",
        do_capture=True,
        region="workspace",
        timeout=60,
    )

    manifest = json.loads((candidate / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert len(manifest) == 1
    entry = manifest[0]
    assert entry["status"] == "captured", entry
    assert (entry["region"], entry["width"], entry["height"]) == ("workspace", *size)

    with Image.open(candidate / "excel" / f"{EXCEL_FIXTURE.name}.png") as img:
        assert img.size == size
        band = img.convert("RGB").crop((0, size[1] - 40, size[0], size[1]))
        colors = band.getcolors(maxcolors=1 << 16) or []
        assert not (len(colors) == 1 and colors[0][1] == (255, 255, 255)), "bottom band is padded white"
        # The sheet tab strip and scrollbar chrome are not white.
        non_white = sum(n for n, c in colors if c != (255, 255, 255))
        assert non_white > size[0] * 5
