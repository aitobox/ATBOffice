"""Tests for scripts/source_diff.py and scripts/parity.py audit tooling."""

from pathlib import Path

import pytest

from scripts.parity import ParityCalculator
from scripts.source_diff import SourceDiffAuditor


def test_source_diff_auditor_clean():
    """Verify that current codebase has 0 orphan controls and 0 stubs."""
    root_dir = Path(__file__).resolve().parent.parent
    auditor = SourceDiffAuditor(root_dir)
    res = auditor.audit()

    assert res["orphan_count"] == 0, f"Found orphan controls: {res['orphans']}"
    assert res["stub_count"] == 0, f"Found stub methods: {res['stubs']}"


def test_source_diff_detects_stub(tmp_path):
    """Verify that SourceDiffAuditor correctly detects stub implementations."""
    src_dir = tmp_path / "src" / "atboffice" / "dummy"
    src_dir.mkdir(parents=True)
    stub_file = src_dir / "stub_sample.py"
    stub_file.write_text(
        "class ConcreteWorker:\n"
        "    def do_work(self):\n"
        "        raise NotImplementedError('not implemented')\n",
        encoding="utf-8",
    )

    auditor = SourceDiffAuditor(tmp_path)
    res = auditor.audit()
    assert res["stub_count"] >= 1
    assert any(s["method"] == "do_work" for s in res["stubs"])


def test_parity_calculator_structure():
    """Verify that ParityCalculator parses features.csv correctly."""
    root_dir = Path(__file__).resolve().parent.parent
    csv_path = root_dir / "docs" / "clone" / "features.csv"
    calc = ParityCalculator(csv_path)
    res = calc.calculate()

    assert res["total_features"] > 100
    assert "overall_weighted_score" in res
    assert "verdict" in res
    assert res["must"]["completed"] == 75
    assert res["must"]["total"] == 75
    assert res["must"]["blockers"] == 0
    assert len(res["domains"]) > 0


def test_parity_calculator_markdown_rendering():
    """Verify markdown output formatting."""
    root_dir = Path(__file__).resolve().parent.parent
    csv_path = root_dir / "docs" / "clone" / "features.csv"
    calc = ParityCalculator(csv_path)
    res = calc.calculate()
    md = calc.render_markdown(res)

    assert "### 1.1 Parity Metrics & Shippability Verdict" in md
    assert "### 1.2 Parity Breakdown by Domain Area" in md
    assert "| **Overall Parity Score** |" in md


def test_parity_calculator_synthetic(tmp_path):
    """Verify calculation arithmetic on synthetic feature set."""
    csv_file = tmp_path / "features.csv"
    csv_file.write_text(
        "feature,area,priority,original,clone,notes\n"
        "F1,core,must,yes,yes,Done\n"
        "F2,core,should,yes,yes,Done\n"
        "F3,core,could,yes,no,Pending\n",
        encoding="utf-8",
    )

    calc = ParityCalculator(csv_file)
    res = calc.calculate()

    # must: 1 * 3 = 3, should: 1 * 2 = 2, could: 0 * 1 = 0 -> total score = 5
    # max possible: 3 + 2 + 1 = 6
    # 5 / 6 = 83.333%
    assert res["total_features"] == 3
    assert pytest.approx(res["overall_weighted_score"], 0.1) == 83.3
    assert res["verdict"] == "SHIPPABLE"
